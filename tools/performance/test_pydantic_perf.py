"""Test Pydantic parsing performance with large payloads."""
import time
import json
from pydantic import BaseModel
from typing import List, Optional

class Message(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    model: str
    messages: List[Message]
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    stream: Optional[bool] = False

# Simulate 36KB payload (like base64 image)
s = time.perf_counter()
data = json.dumps({
    'model': 'gpt-4o',
    'messages': [{'role': 'user', 'content': 'x' * 30000}]
})
print(f'JSON create: {(time.perf_counter()-s)*1000:.2f}ms')

# JSON parsing
s = time.perf_counter()
parsed = json.loads(data)
print(f'JSON parse: {(time.perf_counter()-s)*1000:.2f}ms')

# Pydantic validation
s = time.perf_counter()
req = ChatRequest(**parsed)
print(f'Pydantic validate: {(time.perf_counter()-s)*1000:.2f}ms')

# Pydantic serialization
s = time.perf_counter()
output = req.model_dump_json()
print(f'Pydantic serialize: {(time.perf_counter()-s)*1000:.2f}ms')
