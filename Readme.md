title: Tds Project 1 Main

Running Rounds via PowerShell

This guide explains how to submit tasks (Round 1, Round 2, etc.) to your web app / AI backend using PowerShell commands.

Prerequisites

PowerShell installed on your system (Windows 10/11 has it by default).

Internet connection.

API endpoint (e.g., HF Space URL) and a valid secret/key.

General Structure of a Submission Command

# Define the task payload
$body = @{
    email = "email@example.com"
    secret = "SECRET_KEY"              # My secret / API key
    task = "TASK_NAME"                      
    round = 1                                # Round number (1 or 2)
    nonce = "UNIQUE_NONCE"                   
    brief = "Brief description of the task"
    checks = @(                              
        "Repo has MIT license",
        "README.md is professional"
    )
    evaluation_url = "https://example.com/notify" # Optional: evaluation callback
    attachments = @()                         # Optional attachments
} | ConvertTo-Json -Depth 6

# Send request to API
$response = Invoke-RestMethod `
    -Uri "https://huggingface.co/spaces/abirsaha/tds-project-1-main/api-endpoint" `
    -Method POST `
    -Body $body `
    -ContentType "application/json"

# Show response
Write-Host "Response:"
$response
