"""A scripted two-turn agent loop whose first turn streams before its tool call."""

from collections.abc import AsyncIterator
from typing import Any

from langchain_core.callbacks import (
    AsyncCallbackManagerForLLMRun,
    CallbackManagerForLLMRun,
)
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult
from langgraph.graph import END, START, StateGraph
from pydantic import PrivateAttr

from tests.graph.support.schemas import MessageState

FIRST_TURN_TEXT = "Looking up the datasheet first."
FINAL_ANSWER = "The datasheet says 42."
TOOL_CALL_ID = "call_lookup"


class ScriptedAgentModel(BaseChatModel):
    """Serve scripted assistant turns in order, one per invocation.

    ``_astream`` keeps turn text flowing through LangGraph's ``messages``
    stream mode, mirroring a model that streams text before its tool calls.
    """

    turns: list[AIMessage]
    _cursor: int = PrivateAttr(default=0)

    @property
    def _llm_type(self) -> str:
        return "scripted-agent-model"

    def _next_turn(self) -> AIMessage:
        turn = self.turns[min(self._cursor, len(self.turns) - 1)]
        self._cursor += 1
        return turn

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        return ChatResult(generations=[ChatGeneration(message=self._next_turn())])

    async def _astream(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: AsyncCallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[ChatGenerationChunk]:
        turn = self._next_turn()
        yield ChatGenerationChunk(
            message=AIMessageChunk(
                content=str(turn.text),
                tool_calls=list(turn.tool_calls),
            )
        )


def make_agent_loop_graph() -> Any:
    """Compile a two-turn agent: streamed text plus a tool call, then the answer."""
    model = ScriptedAgentModel(
        turns=[
            AIMessage(
                content=FIRST_TURN_TEXT,
                tool_calls=[
                    {
                        "name": "lookup",
                        "args": {},
                        "id": TOOL_CALL_ID,
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(content=FINAL_ANSWER),
        ]
    )

    async def agent(state: MessageState) -> dict[str, list[BaseMessage]]:
        return {"messages": [await model.ainvoke(state["messages"])]}

    async def run_tools(state: MessageState) -> dict[str, list[BaseMessage]]:
        last = state["messages"][-1]
        if not isinstance(last, AIMessage):
            return {"messages": []}
        return {
            "messages": [
                ToolMessage(
                    content="ok",
                    tool_call_id=call["id"],
                    name=call["name"],
                )
                for call in last.tool_calls
            ]
        }

    def route(state: MessageState) -> str:
        last = state["messages"][-1]
        if not isinstance(last, AIMessage):
            return END
        return "tools" if last.tool_calls else END

    return (
        StateGraph(MessageState)
        .add_node("agent", agent)
        .add_node("tools", run_tools)
        .add_edge(START, "agent")
        .add_conditional_edges("agent", route)
        .add_edge("tools", "agent")
        .compile()
    )
