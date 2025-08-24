import json
from datetime import datetime


class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        elif hasattr(obj, 'model_dump'):  # For Pydantic models (like ChatCompletionStreamResponse)
            return obj.model_dump()
        elif hasattr(obj, 'dict'):  # Fallback for older Pydantic versions
            return obj.dict()
        return super().default(obj)
