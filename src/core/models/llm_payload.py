from pydantic import BaseModel
from typing import List, Dict, Any, Optional

class ChatCompletionRequest(BaseModel):
    """
    ChatCompletionRequest is a model representing the payload for a chat completion request.

    Attributes:
        model (str): The name of the model to use for the chat completion.
        messages (List[Dict[str, Any]]): A list of message objects, where each message is a dictionary
            containing the role (e.g., "user", "assistant") and the content of the message.
        temperature (Optional[float]): Sampling temperature to control randomness. Higher values (e.g., 1.0)
            make the output more random, while lower values (e.g., 0.2) make it more focused and deterministic.
            Defaults to 1.0.
        top_p (Optional[float]): Nucleus sampling parameter. When set to a value between 0 and 1, it limits
            the model to consider only the most probable tokens whose cumulative probability is less than top_p.
            Defaults to 1.0.
        n (Optional[int]): The number of completions to generate for each input message. Defaults to 1.
        stream (Optional[bool]): Whether to stream partial message deltas as they become available.
            Defaults to False.
        stop (Optional[List[str]]): A list of sequences where the API will stop generating further tokens.
            Defaults to None.
        max_tokens (Optional[int]): The maximum number of tokens to generate in the completion.
            Defaults to None.
        presence_penalty (Optional[float]): A penalty applied to encourage the model to talk about new topics.
            Positive values penalize tokens that appear in the context. Defaults to 0.0.
        frequency_penalty (Optional[float]): A penalty applied to reduce the likelihood of repeating the same
            tokens. Positive values penalize tokens based on their frequency in the context. Defaults to 0.0.
        logit_bias (Optional[Dict[str, float]]): A dictionary mapping token IDs to bias values, where positive
            values increase the likelihood of the token appearing, and negative values decrease it. Defaults to None.
        user (Optional[str]): An identifier for the end-user making the request. This can help with monitoring
            and abuse detection. Defaults to None.
    """
    model: str
    messages: List[Dict[str, Any]]
    temperature: Optional[float] = 1.0
    top_p: Optional[float] = 1.0
    n: Optional[int] = 1
    stream: Optional[bool] = False
    stop: Optional[List[str]] = None
    max_tokens: Optional[int] = None
    presence_penalty: Optional[float] = 0.0
    frequency_penalty: Optional[float] = 0.0
    logit_bias: Optional[Dict[str, float]] = None
    user: Optional[str] = None

