import os
from deepeval import evaluate
from deepeval.metrics import FaithfulnessMetric, AnswerRelevancyMetric
from deepeval.test_case import LLMTestCase
from deepeval.models.base_model import DeepEvalBaseLLM
from groq import Groq
import time

groq_client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

class GroqJudge(DeepEvalBaseLLM):
    """
    Wraps Groq API so deepeval uses llama3 as judge
    without needing local Ollama.
    """
    def __init__(self, model: str = "llama-3.3-70b-versatile", max_retries: int = 3):
        self.model       = model
        self.max_retries = max_retries

    def load_model(self):
        return self.model

    def generate(self, prompt: str) -> str:
        last_error = None
        for attempt in range(self.max_retries):
            try:
                response = groq_client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.0,
                )
                return response.choices[0].message.content
            except Exception as e:
                last_error = e
                print(f"  ⚠️  GroqJudge attempt {attempt + 1} failed: {e}")
        raise last_error

    async def a_generate(self, prompt: str) -> str:
        return self.generate(prompt)

    def get_model_name(self) -> str:
        return f"groq/{self.model}"


def run_llm_evals(insight: dict, metrics: dict) -> dict:
    try:
        time.sleep(20)
        actual_output = " ".join([
            insight.get("trend_insights", ""),
            insight.get("anomaly_insights", ""),
            insight.get("contribution_insights", ""),
        ])

        retrieval_context = [str(metrics)]

        test_case = LLMTestCase(
            input="Generate business insights summarising these retail analytics results.",
            actual_output=actual_output,
            retrieval_context=retrieval_context,
        )

        judge        = GroqJudge()
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

    except Exception as e:
        print(f"  ⚠️  LLM eval failed: {e}")
        return {
            "faithfulness_score":  None,
            "faithfulness_reason": "Judge model failed",
            "relevancy_score":     None,
            "relevancy_reason":    "Judge model failed",
            "passed":              None,
        }