"""Local adapter checks: no test calls a real model or a paid service."""
import json

import httpx
import pytest

from energy_agent.llm import LLMError, OpenAICompatibleClient, RuleClient, get_llm_client
from energy_agent.schemas import TaskRequest


def completion(arguments, *, name="propose_task_patch", content=None, repeat=1):
    return {
        "choices": [{"message": {
            "role": "assistant", "content": content,
            "tool_calls": [{"id": "call_1", "type": "function", "function": {
                "name": name,
                "arguments": arguments if isinstance(arguments, str) else json.dumps(arguments),
            }}] * repeat,
        }}],
    }


def adapter(responses, requests):
    pending = iter(responses)

    def handler(request):
        requests.append(request)
        response = next(pending)
        return response if isinstance(response, httpx.Response) else httpx.Response(200, json=response)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    return OpenAICompatibleClient("https://model.invalid/v1", "test-model", "test-key", client=client)


def test_valid_patch_uses_only_registered_tool_and_minimal_context():
    requests = []
    model = adapter([completion({"budget_yuan": 450000, "demand_scale": 1.2})], requests)
    patch = model.parse_patch("预算改为45万元，负荷提高20%", TaskRequest())
    assert patch.budget_yuan == 450000
    assert patch.demand_scale == 1.2
    request = json.loads(requests[0].content)
    assert str(requests[0].url) == "https://model.invalid/v1/chat/completions"
    assert [tool["function"]["name"] for tool in request["tools"]] == ["propose_task_patch"]
    assert request["tool_choice"]["function"]["name"] == "propose_task_patch"
    assert request["tools"][0]["function"]["parameters"]["additionalProperties"] is False
    assert "data" not in json.loads(request["messages"][1]["content"])["current_task"]


def test_invalid_model_result_retries_then_uses_valid_patch():
    requests = []
    model = adapter([
        completion({"budget_yuan": -1}),
        completion("not JSON"),
        completion({"budget_yuan": 500000}),
    ], requests)
    assert model.parse_patch("预算50万元", TaskRequest()).budget_yuan == 500000
    assert len(requests) == 3
    assert "未通过校验" in json.loads(requests[1].content)["messages"][-1]["content"]


@pytest.mark.parametrize("bad", [
    completion({"investment_yuan": 1, "operating_cost_yuan": 2}),
    completion({}, name="execute_python"),
    completion({}, repeat=2),
    completion({}, content="已算出投资为1元"),
    completion({"clear_emission_limit": True, "emission_limit_kg": 10}),
    {"choices": []},
])
def test_unregistered_tools_invented_results_and_invalid_outputs_fail_closed(bad):
    requests = []
    model = adapter([bad, bad, bad], requests)
    with pytest.raises(LLMError, match="连续 3 次"):
        model.parse_patch("调整任务", TaskRequest())
    assert len(requests) == 3


def test_no_configuration_never_calls_network_and_describes_rule_limitations():
    def forbidden(request):
        pytest.fail("rule mode must not make HTTP requests")

    client = httpx.Client(transport=httpx.MockTransport(forbidden))
    for env in ({}, {"LLM_BASE_URL": "https://model.invalid/v1", "LLM_MODEL": "test"}):
        model = get_llm_client(env, client=client)
        assert isinstance(model, RuleClient)
        with pytest.raises(LLMError, match="不支持任意自然语言"):
            model.parse_patch("帮我评估园区", TaskRequest())


def test_configured_client_does_not_call_model_until_explicit_parse():
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json=completion({"budget_yuan": 100000}))

    client = httpx.Client(transport=httpx.MockTransport(handler))
    model = get_llm_client({
        "LLM_BASE_URL": "https://model.invalid/v1",
        "LLM_MODEL": "test", "LLM_API_KEY": "test-key",
    }, client=client)
    assert calls == []
    assert model.parse_patch("预算10万元", TaskRequest()).budget_yuan == 100000
    assert len(calls) == 1


def test_unsupported_demand_is_preserved_even_if_model_omits_it():
    requests = []
    model = adapter([completion({"budget_yuan": 100000})], requests)
    task = TaskRequest(unsupported_demands=["用户要求尚未支持的设备故障备用"])
    patch = model.parse_patch("预算10万元，并考虑供冷和售电", task)
    assert any("供冷" in demand for demand in patch.unsupported_demands)
    assert any("售电" in demand for demand in patch.unsupported_demands)
    assert task.unsupported_demands[0] in patch.unsupported_demands


def test_model_extracted_unsupported_demand_is_not_lost():
    model = adapter([completion({"unsupported_demands": ["供冷"]})], [])
    assert model.parse_patch("增加供冷", TaskRequest()).unsupported_demands == ["供冷"]


@pytest.mark.parametrize("text", ["不要供冷", "本次不考虑供冷和售电", "without cooling"])
def test_explicit_exclusion_is_not_misclassified_as_unsupported_demand(text):
    model = adapter([completion({})], [])
    assert model.parse_patch(text, TaskRequest()).unsupported_demands == []


def test_exclusion_does_not_mask_a_later_positive_request():
    model = adapter([completion({})], [])
    patch = model.parse_patch("不要供冷但需要售电", TaskRequest())
    assert not any("供冷" in value for value in patch.unsupported_demands)
    assert any("售电" in value for value in patch.unsupported_demands)


def test_http_failure_is_not_retried_and_does_not_expose_response_or_credentials():
    requests = []
    model = adapter([httpx.Response(401, text="private-response test-key")], requests)
    with pytest.raises(LLMError, match="HTTP 401") as error:
        model.parse_patch("预算10万元", TaskRequest())
    assert "test-key" not in str(error.value)
    assert "private-response" not in str(error.value)
    assert len(requests) == 1


def test_transport_failure_hides_provider_url_and_credentials():
    def handler(request):
        raise httpx.ConnectError("private test-key", request=request)

    model = OpenAICompatibleClient(
        "https://model.invalid/v1", "test", "test-key",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    with pytest.raises(LLMError, match="连接失败") as error:
        model.parse_patch("预算10万元", TaskRequest())
    assert "test-key" not in str(error.value)


def test_blank_prompt_and_invalid_service_root_are_rejected_before_request():
    model = adapter([], [])
    with pytest.raises(LLMError, match="请输入"):
        model.parse_patch(" ", TaskRequest())
    with pytest.raises(LLMError, match="API 根地址"):
        OpenAICompatibleClient("https://private:key@model.invalid/v1", "test", "test-key")
