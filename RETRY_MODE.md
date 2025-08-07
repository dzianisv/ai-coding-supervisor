# VibeTeam Task Retry Mode

The `vibeteam-task` command now supports automatic retry functionality to handle transient failures, especially **Claude usage limits**.

## Overview

When Claude's usage limit is reached, tasks would previously fail completely. With retry mode, the system will automatically wait and retry the task when the quota resets, ensuring your automation continues running even during high usage periods.

## Quick Start

```bash
# Enable retry with default settings (recommended)
vibeteam-task --retry

# Retry with custom parameters
vibeteam-task --retry --max-attempts 5 --base-delay 120
```

## When Retry Triggers

Retry mode automatically detects and retries these error types:

### ✅ **Transient Errors (Retryable)**
- **Claude usage limit reached** ⭐ *Most common case*
- API rate limiting (429 errors)
- Timeouts and temporary service unavailability  
- Network connection issues
- Temporary API failures (502, 503, 504)

### ❌ **Implementation Errors (Not Retryable)**
- Syntax errors in generated code
- Logic bugs in implementation
- Missing dependencies
- File permission issues

## Retry Behavior

### Exponential Backoff with Jitter
```
Attempt 1: Wait 1 minute
Attempt 2: Wait 2 minutes  
Attempt 3: Wait 4 minutes
Attempt 4: Wait 8 minutes
...continuing until max delay reached
```

### Smart Timing
- **Base delay**: 60 seconds (1 minute) - good for usage limit resets
- **Max delay**: 3600 seconds (1 hour) - prevents extremely long waits
- **Jitter**: ±25% random variation to avoid thundering herd problems

## Configuration Options

| Option | Default | Description |
|--------|---------|-------------|
| `--retry` | disabled | Enable retry functionality |
| `--max-attempts` | 3 | Maximum number of retry attempts |
| `--base-delay` | 60.0 | Base delay in seconds before first retry |
| `--max-delay` | 3600.0 | Maximum delay in seconds between retries |

## Usage Examples

### Basic Retry (Recommended)
```bash
vibeteam-task --retry
```
- Retries up to 3 times
- Starts with 1-minute delay
- Good for most Claude usage limit scenarios

### High-Volume Scenarios  
```bash
vibeteam-task --retry --max-attempts 5 --base-delay 120
```
- Retries up to 5 times
- Starts with 2-minute delay
- Better for heavy usage periods

### Quick Development
```bash
vibeteam-task --retry --base-delay 30 --max-delay 300
```
- Shorter delays for faster feedback
- Good for development/testing

### Production Long-Running
```bash
vibeteam-task --retry --max-attempts 10 --max-delay 7200
```
- More attempts for reliability
- Allows up to 2-hour delays
- Good for overnight batch processing

## Combining with Reflection

```bash
vibeteam-task --retry --enable-reflection
```

When combined with reflection mode, the system can:
- Distinguish between transient errors (API limits) and implementation issues
- Use appropriate retry strategies for each error type
- Provide detailed analysis of why retries occurred

## Monitoring Retry Behavior

When retry mode is active, you'll see detailed output:

```
🔄 Retry mode enabled - max 3 attempts with exponential backoff
⚠️  Detected retryable error: Claude usage limit reached...
⏱️  Waiting 1.2m before retry...
🔄 Retry attempt 2/3
```

## Best Practices

### ✅ **Do**
- Use `--retry` for production automation
- Monitor logs for retry patterns
- Adjust delays based on your usage patterns
- Combine with `--enable-reflection` for better error analysis

### ❌ **Don't**  
- Set extremely short delays (< 30 seconds)
- Use excessive retry attempts (> 10) 
- Ignore retry logs - they indicate usage patterns
- Disable retry in production environments

## Troubleshooting

### Issue: Too Many Retries
**Solution**: You may be hitting sustained usage limits
```bash
# Increase delays and reduce attempts
vibeteam-task --retry --max-attempts 3 --base-delay 300
```

### Issue: Retries Taking Too Long
**Solution**: Reduce maximum delay
```bash
# Cap delays at 30 minutes
vibeteam-task --retry --max-delay 1800
```

### Issue: Non-Retryable Errors Keep Retrying
**Solution**: Check if reflection mode can help distinguish error types
```bash
vibeteam-task --retry --enable-reflection
```

## Integration with CI/CD

For automated environments:

```bash
# Reliable but patient
vibeteam-task --retry --max-attempts 5 --base-delay 180

# Or use environment variables in your CI config
export VIBETEAM_RETRY_ENABLED=true
export VIBETEAM_MAX_ATTEMPTS=3
export VIBETEAM_BASE_DELAY=120
```

---

The retry feature makes VibeTeam task automation much more robust in real-world usage scenarios, especially when dealing with Claude's usage limits during peak periods.