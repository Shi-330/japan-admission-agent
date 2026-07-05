# Claude Code + DeepSeek (Anthropic endpoint). Run: .\start-claude.ps1
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$env:ANTHROPIC_BASE_URL = "https://api.deepseek.com/anthropic"
$env:ANTHROPIC_MODEL = "deepseek-v4-pro[1m]"
$env:ANTHROPIC_DEFAULT_OPUS_MODEL = "deepseek-v4-pro[1m]"
$env:ANTHROPIC_DEFAULT_SONNET_MODEL = "deepseek-v4-pro[1m]"
$env:ANTHROPIC_DEFAULT_HAIKU_MODEL = "deepseek-v4-flash"
$env:CLAUDE_CODE_SUBAGENT_MODEL = "deepseek-v4-flash"
$env:CLAUDE_CODE_EFFORT_LEVEL = "medium"

foreach ($name in @("OPENAI_API_KEY", "OPENAI_BASE_URL", "OPENAI_API_BASE", "ANTHROPIC_API_KEY")) {
    if (Get-Item "Env:$name" -ErrorAction SilentlyContinue) {
        Write-Warning "Removed $name (use ANTHROPIC_AUTH_TOKEN for DeepSeek)."
        Remove-Item "Env:$name"
    }
}

# API key: .deepseek-api-key > user settings.json > project settings.local.json
$keyFile = Join-Path $PSScriptRoot ".deepseek-api-key"
if (Test-Path $keyFile) {
    $env:ANTHROPIC_AUTH_TOKEN = (Get-Content $keyFile -Raw).Trim()
}
if (-not $env:ANTHROPIC_AUTH_TOKEN) {
    $userSettings = Join-Path $env:USERPROFILE ".claude\settings.json"
    if (Test-Path $userSettings) {
        $token = (Get-Content $userSettings -Raw | ConvertFrom-Json).env.ANTHROPIC_AUTH_TOKEN
        if ($token -and $token -ne "YOUR_DEEPSEEK_API_KEY_HERE") {
            $env:ANTHROPIC_AUTH_TOKEN = $token
        }
    }
}
if (-not $env:ANTHROPIC_AUTH_TOKEN) {
    $localSettings = Join-Path $PSScriptRoot ".claude\settings.local.json"
    if (Test-Path $localSettings) {
        $local = Get-Content $localSettings -Raw | ConvertFrom-Json
        if ($local.env.ANTHROPIC_AUTH_TOKEN) {
            $token = $local.env.ANTHROPIC_AUTH_TOKEN
            if ($token -eq "YOUR_DEEPSEEK_API_KEY_HERE") {
                Write-Warning "Ignore placeholder in .claude\settings.local.json; use user settings or .deepseek-api-key"
            } elseif ($token) {
                $env:ANTHROPIC_AUTH_TOKEN = $token
            }
        }
    }
}

if (-not $env:ANTHROPIC_AUTH_TOKEN) {
    Write-Host ""
    Write-Host "DeepSeek API key not set. Use one of:" -ForegroundColor Yellow
    Write-Host "  - .deepseek-api-key (one line, sk-...)"
    Write-Host "  - %USERPROFILE%\.claude\settings.json -> ANTHROPIC_AUTH_TOKEN"
    Write-Host "  - .claude\settings.local.json -> ANTHROPIC_AUTH_TOKEN"
    Write-Host ""
    Write-Host "Endpoint: $env:ANTHROPIC_BASE_URL"
    Write-Host "Model:    $env:ANTHROPIC_MODEL"
    Write-Host ""
}

# Uncomment if you need Clash proxy:
# $env:HTTP_PROXY  = "http://127.0.0.1:33210"
# $env:HTTPS_PROXY = "http://127.0.0.1:33210"

Write-Host "Claude Code -> $env:ANTHROPIC_BASE_URL" -ForegroundColor Cyan
Write-Host "Project:     $PSScriptRoot" -ForegroundColor Cyan
claude
