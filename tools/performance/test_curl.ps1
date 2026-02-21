# Test avec mesure TTFB (Time To First Byte) - VERSION AVEC IMAGE
# Function to encode image to base64
function Get-ImageBase64 {
    param([string]$imagePath)
    $imageBytes = [System.IO.File]::ReadAllBytes($imagePath)
    return [System.Convert]::ToBase64String($imageBytes)
}

# Load and encode image
$imagePath = "C:\Users\Administrator\OneDrive\Images\226px-Jenkins_logo.svg.png"
Write-Host "📸 Loading image: $imagePath"
$imageBase64 = Get-ImageBase64 -imagePath $imagePath
Write-Host "   Image size: $($imageBase64.Length) bytes (base64)"

# Create payload with image
$body = @{
    model = "gpt-4o"
    messages = @(
        @{
            role = "user"
            content = @(
                @{
                    type = "text"
                    text = "Describe this image"
                }
                @{
                    type = "image_url"
                    image_url = @{
                        url = "data:image/png;base64,$imageBase64"
                    }
                }
            )
        }
    )
} | ConvertTo-Json -Depth 10

$headers = @{
    "Authorization" = "Bearer sk-920xAa9zy_C8jixH9Q-9Jdp09_y7RxjXRTKK39HHp54"
    "Content-Type" = "application/json"
}

Write-Host "Starting request..."
$start = Get-Date
$ttfb = $null
$responseReceived = $false

try {
    # Utiliser HttpClient pour mesurer TTFB
    Add-Type -AssemblyName System.Net.Http
    $httpClient = New-Object System.Net.Http.HttpClient
    $httpClient.Timeout = [TimeSpan]::FromSeconds(30)

    $content = New-Object System.Net.Http.StringContent($body, [System.Text.Encoding]::UTF8, "application/json")
    $content.Headers.ContentType = "application/json"

    $request = New-Object System.Net.Http.HttpRequestMessage([System.Net.Http.HttpMethod]::Post, "http://localhost:8000/v1/chat/completions")
    $request.Content = $content
    $request.Headers.Add("Authorization", "Bearer sk-920xAa9zy_C8jixH9Q-9Jdp09_y7RxjXRTKK39HHp54")

    Write-Host "⏱️  Request sent at $((Get-Date).ToString('HH:mm:ss.fff'))"

    $responseTask = $httpClient.SendAsync($request, [System.Net.Http.HttpCompletionOption]::ResponseHeadersRead)
    $responseTask.Wait()
    $response = $responseTask.Result

    $ttfb = (Get-Date) - $start
    Write-Host "🎯 TTFB (headers received): $($ttfb.TotalMilliseconds) ms"

    # Now read the body
    $bodyStart = Get-Date
    $bodyTask = $response.Content.ReadAsStringAsync()
    $bodyTask.Wait()
    $responseBody = $bodyTask.Result
    $bodyTime = (Get-Date) - $bodyStart

    $totalTime = (Get-Date) - $start
    Write-Host "📦 Body download: $($bodyTime.TotalMilliseconds) ms"
    Write-Host "⏱️  Total time: $($totalTime.TotalMilliseconds) ms"
    Write-Host "📊 Status: $($response.StatusCode)"
    Write-Host "📏 Content length: $($responseBody.Length) bytes"

    $json = $responseBody | ConvertFrom-Json
    Write-Host "🤖 Model: $($json.model)"
    Write-Host "💬 Content: $($json.choices[0].message.content)"

    $httpClient.Dispose()
}
catch {
    Write-Host "❌ Error: $_"
}
