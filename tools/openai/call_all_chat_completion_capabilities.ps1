# script use arguments to get the model and  select capabilities to test
Param(
    [ValidateSet("gpt-4.1", "gpt-4o", "grok", "gpt-5-chat")]
    [string]$model = "gpt-4.1",
    [switch]$TestStreaming,
    [switch]$TestFunctionCalling,
    [switch]$TestFileUpload,
    [switch]$TestFollowUp
)

# Basic question
python .\tools\openai\openai_call_chat_completions.py `
       --model $model

# Streaming
if ($TestStreaming) {
    python .\tools\openai\openai_call_chat_completions.py `
        --question "peux tu traduire en français: The following example demonstrates how to use the fictitious MCP server to query information about the Azure REST API. This allows the model to retrieve and reason over repository content in real time." `
        --model $model `
        --stream
}

# Question on images with streaming
if ($TestFileUpload -and $TestStreaming) {
    python .\tools\openai\openai_call_chat_completions.py `
       --question "describe this file" `
       --model $model `
       --file-path "C:\Users\Administrator\Pictures\226px-Jenkins_logo.svg.png" `
       --stream
}

# Question on images with streaming
if ($TestFileUpload -and $TestStreaming) {
    python .\tools\openai\openai_call_chat_completions.py `
       --question "describe this file" `
       --model $model `
       --file-path "C:\Users\Administrator\Pictures\226px-Jenkins_logo.svg.png"
}


# Question with previous response id
if ($TestFollowUp) {
    python .\tools\openai\openai_call_chat_completions.py `
      --question "peux tu traduire en français: The following example demonstrates how to use the fictitious MCP server to query information about the Azure REST API. This allows the model to retrieve and reason over repository content in real time." `
      --model $model `
      --follow-up "et en espagnol" `
      --use-previous
}

# Call function
if ($TestFunctionCalling) {
    python .\tools\openai\openai_call_chat_completions.py `
       --question "what time is it at paris" `
       --model $model `
       --function-tool
}

# Call function with follow-up using previous response messages
if ($TestFunctionCalling -and $TestFollowUp) {
    python .\tools\openai\openai_call_chat_completions.py `
       --question "what time is it at paris" `
       --model $model `
       --function-tool `
       --follow-up "dans combien de temps il est minuit?"
}
