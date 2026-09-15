import json
import logging

from langchain_core.messages import AIMessage

from app.services import llm


class ModelWithUsage:
    def invoke(self, messages):
        return AIMessage(
            content="hello",
            response_metadata={
                "token_usage": {
                    "prompt_tokens": 100,
                    "completion_tokens": 25,
                    "total_tokens": 125,
                }
            },
        )


def test_invoke_logs_versioned_usage_and_cost(caplog):
    with caplog.at_level(logging.INFO, logger=llm.__name__):
        result = llm.invoke(ModelWithUsage(), [])

    assert result.content == "hello"
    event = json.loads(caplog.records[-1].message)
    assert event["event"] == "llm_invocation"
    assert event["success"] is True
    assert event["prompt_version"] == "1.0.0"
    assert event["input_tokens"] == 100
    assert event["output_tokens"] == 25
    assert event["estimated_cost_usd"] == 0.00003