# script use arguments to get the model and  select capabilities to test
Param(
    [string]$model = "gpt-4.1",
    [switch]$TestStreaming,
    [switch]$TestFunctionCalling,
    [switch]$TestFileUpload,
    [switch]$TestFollowUp
)

# Basic question
python .\tools\openai\openai_call_responses_api.py `
      --model $model

# Streaming
if ($TestStreaming) {
    python .\tools\openai\openai_call_responses_api.py `
        --question "peux tu traduire en français: The following example demonstrates how to use the fictitious MCP server to query information about the Azure REST API. This allows the model to retrieve and reason over repository content in real time." `
        --model $model `
        --stream
}

# Question with previous response id
if ($TestFollowUp) {
    python .\tools\openai\openai_call_responses_api.py `
      --question "peux tu traduire en français: The following example demonstrates how to use the fictitious MCP server to query information about the Azure REST API. This allows the model to retrieve and reason over repository content in real time." `
      --model $model `
      --follow-up "et en espagnol" `
      --use-previous
}

# Question on images with streaming
if ($TestFileUpload -and $TestStreaming) {
    python .\tools\openai\openai_call_responses_api.py `
       --question "describe this file" `
       --model $model `
       --file-path "C:\Users\Administrator\Pictures\226px-Jenkins_logo.svg.png" `
       --stream
}

# Question on documents
if ($TestFileUpload) {
    python .\tools\openai\openai_call_responses_api.py `
        --question "describe this document" `
        --model $model `
        --file-path "D:\OneDrive\Documents\voyages\Sicile\assurances\Résumé police d'assurance dommages et responsabilité civile.pdf"
}

# Call function
if ($TestFunctionCalling) {
    python .\tools\openai\openai_call_responses_api.py `
       --question "what time is it at paris" `
       --model $model `
       --function-tool
}

# Call function with follow-up using previous response messages
if ($TestFunctionCalling -and $TestFollowUp) {
    python .\tools\openai\openai_call_responses_api.py `
       --question "what time is it at paris" `
       --model $model `
       --function-tool `
       --follow-up "dans combien de temps il est minuit?"
}

# Call function with follow-up using previous response id
if ($TestFunctionCalling -and $TestFollowUp) {
python .\tools\openai\openai_call_responses_api.py `
       --question "what time is it at paris" `
       --model $model `
       --function-tool `
       --follow-up "dans combien de temps il est minuit?" `
       --use-previous
}