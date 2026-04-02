# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
You can add your unit tests here.
This is where you test your business logic, including agent functionality,
data processing, and other core components of your application.
"""

from deepeval import assert_test
from deepeval.test_case import LLMTestCase
from deepeval.metrics import AnswerRelevancyMetric
from tests.unit.claude_judge import ClaudeJudge

def test_financial_relevancy():
    # 1. The scenario
    input_text = "What is the revenue for MCD_1 in Oct 2025?"
    
    # 2. Simulated output from your FP&A Agent
    actual_output = "In Oct 2025, the revenue for MCD_1 was $440k."
    
    # 3. Initialize your direct Anthropic Claude Judge
    claude_model = ClaudeJudge()
    
    # 4. Set up the Metric
    relevancy_metric = AnswerRelevancyMetric(threshold=0.7, model=claude_model)
    
    # 5. Create the Test Case
    test_case = LLMTestCase(
        input=input_text,
        actual_output=actual_output
    )
    
    # 6. Run the test
    assert_test(test_case, [relevancy_metric])