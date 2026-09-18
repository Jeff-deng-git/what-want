$ErrorActionPreference = "Stop"

$key = [Environment]::GetEnvironmentVariable("DEEPSEEK_API_KEY", "Process")
if ([string]::IsNullOrWhiteSpace($key)) {
    Write-Output "key=missing"
    exit 2
}

Write-Output "key=present length=$($key.Length)"

$payload = @{
    model = "deepseek-v4-flash"
    messages = @(
        @{
            role = "user"
            content = "Reply only OK"
        }
    )
    max_tokens = 20
} | ConvertTo-Json -Depth 5 -Compress

try {
    $response = Invoke-WebRequest `
        -UseBasicParsing `
        -Method Post `
        -Uri "https://api.deepseek.com/v1/chat/completions" `
        -Headers @{ Authorization = "Bearer $key" } `
        -ContentType "application/json" `
        -Body $payload `
        -TimeoutSec 45

    Write-Output "status=$($response.StatusCode)"
    exit 0
}
catch {
    if ($null -ne $_.Exception.Response) {
        Write-Output "status=$([int]$_.Exception.Response.StatusCode)"
        exit 3
    }

    Write-Output "request_error=$($_.Exception.Message)"
    exit 4
}
