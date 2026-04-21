from deepeval import evaluate
from deepeval.metrics import FaithfulnessMetric, AnswerRelevancyMetric
from deepeval.test_case import LLMTestCase
from deepeval.models.base_model import DeepEvalBaseLLM
import ollama

# ── Custom Ollama judge model ─────────────────────────────────────────

class OllamaJudge(DeepEvalBaseLLM):
    """
    Wraps local Ollama so deepeval uses Mistral as the judge LLM
    instead of requiring an OpenAI API key.
    """
    def __init__(self, model: str = "mistral"):
        self.model = model

    def load_model(self):
        return self.model

    def generate(self, prompt: str) -> str:
        response = ollama.chat(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
        )
        return response["message"]["content"]

    async def a_generate(self, prompt: str) -> str:
        return self.generate(prompt)

    def get_model_name(self) -> str:
        return f"ollama/{self.model}"


def run_llm_evals(insight: dict, metrics: dict) -> dict:
    """
    LLM-as-judge evaluation using deepeval.
    Complements deterministic factuality checks.
    """
    # Combine all insight fields into one output string
    actual_output = " ".join([
        insight.get("trend_insights", ""),
        insight.get("anomaly_insights", ""),
        insight.get("contribution_insights", ""),
    ])

    # The metrics dict is the retrieval context the LLM was given
    retrieval_context = [str(metrics)]


    test_case = LLMTestCase(
        input=str(metrics),              # what the LLM received
        actual_output=actual_output,     # what the LLM produced
        retrieval_context=retrieval_context,
    )

    judge = OllamaJudge(model="llama3")      # ← local judge

    faithfulness = FaithfulnessMetric(threshold=0.7, model=judge)
    relevancy    = AnswerRelevancyMetric(threshold=0.7, model=judge)

    faithfulness.measure(test_case)
    relevancy.measure(test_case)

    return {
        "faithfulness_score":  faithfulness.score,
        "faithfulness_reason": faithfulness.reason,
        "relevancy_score":     relevancy.score,
        "relevancy_reason":    relevancy.reason,
        "passed":              faithfulness.is_successful() and relevancy.is_successful(),
    }