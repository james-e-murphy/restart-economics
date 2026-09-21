# Facts the manuscript quotes

Written by `paper/facts.py` from `results/`. Do not edit by hand.

## Configurations

| configuration | tasks with four usable draws | median attempt, $ | $ an hour at 1x |
|---|---|---|---|
| GPT-5 | 496 | 0.345 | 0.69 |
| GPT-5.2 | 405 | 0.556 | 1.16 |
| Sonnet 4 | 498 | 1.039 | 2.07 |
| Sonnet 4.5 | 500 | 1.661 | 3.31 |
| Gemini 3 Pro | 410 | 0.815 | 1.66 |
| Kimi K2 | 412 | 0.698 | 1.38 |
| Qwen3 Coder† | 500 | 1.085 | 2.16 |

`$ an hour at 1x` is the rate at which the mean outside option equals one median attempt; a break-even of M times is M times that rate.

## Retry, automated verifier

| configuration | $/h | i | ii | saving | saving % | K chosen |
|---|---|---|---|---|---|---|
| GPT-5 | 25 | 7.54 | 6.5 | 1.04 | 13.8 | 4  |
| GPT-5 | 100 | 28.91 | 23.23 | 5.67 | 19.6 | 4  |
| GPT-5 | 300 | 85.9 | 67.86 | 18.04 | 21.0 | 4  |
| GPT-5.2 | 25 | 6.46 | 6.52 | -0.06 | -0.9 | 1 , 2  |
| GPT-5.2 | 100 | 23.66 | 22.65 | 1.01 | 4.3 | 2 , 3 , 4  |
| GPT-5.2 | 300 | 69.51 | 63.92 | 5.59 | 8.0 | 4  |
| Sonnet 4 | 25 | 7.33 | 7.13 | 0.2 | 2.8 | 2  |
| Sonnet 4 | 100 | 25.47 | 21.76 | 3.71 | 14.6 | 4  |
| Sonnet 4 | 300 | 73.84 | 60.26 | 13.58 | 18.4 | 4  |
| Sonnet 4.5 | 25 | 8.31 | 8.19 | 0.12 | 1.5 | 2  |
| Sonnet 4.5 | 100 | 27.72 | 23.89 | 3.83 | 13.8 | 4  |
| Sonnet 4.5 | 300 | 79.48 | 64.01 | 15.47 | 19.5 | 4  |
| Gemini 3 Pro | 25 | 7.68 | 7.43 | 0.25 | 3.3 | 2  |
| Gemini 3 Pro | 100 | 27.67 | 24.03 | 3.64 | 13.2 | 4  |
| Gemini 3 Pro | 300 | 80.95 | 67.64 | 13.31 | 16.4 | 4  |
| Kimi K2 | 25 | 8.14 | 7.85 | 0.29 | 3.6 | 2  |
| Kimi K2 | 100 | 29.44 | 25.26 | 4.19 | 14.2 | 4  |
| Kimi K2 | 300 | 86.26 | 70.78 | 15.48 | 17.9 | 4  |
| Qwen3 Coder† | 25 | 8.05 | 7.85 | 0.21 | 2.6 | 2  |
| Qwen3 Coder† | 100 | 27.64 | 23.55 | 4.09 | 14.8 | 4  |
| Qwen3 Coder† | 300 | 79.88 | 64.1 | 15.78 | 19.8 | 4  |

## Retry under review: rows where retrying saves anything

regime_name
human 0.1    8
human 0.3    0
human 0.5    0

Rows are configurations x rates on the dollar axis.

## The cap given retry: break-evens and resolution

| regime | configuration | first crossing $/h | x median attempt | crossings | supported | saving resolved up to $/h | saving resolved up to x | rows resolved as a cost | retry beats escalating above x* |
|---|---|---|---|---|---|---|---|---|---|
| automated | GPT-5 | 1.74 | 2.54 | 3 | 0 | 1.37 | 2.0 | 0 | 2.53 |
| automated | GPT-5.2 | 3.36 | 2.89 | 4 | 0 | 1.16 | 1.0 | 0 | 2.38 |
| automated | Sonnet 4 | 4.51 | 2.18 | 1 | 0 | 2.07 | 1.0 | 0 | 2.38 |
| automated | Sonnet 4.5 | 7.08 | 2.14 | 3 | 0 | 5.0 | 1.51 | 0 | 2.24 |
| automated | Gemini 3 Pro | 3.9 | 2.35 | 1 | 0 | 3.32 | 2.0 | 0 | 2.7 |
| automated | Kimi K2 | 5.3 | 3.83 | 1 | 0 | 2.77 | 2.0 | 0 | 3.33 |
| automated | Qwen3 Coder† | 5.91 | 2.73 | 1 | 0 | 4.32 | 2.0 | 0 | 2.78 |
| human 0.1 | GPT-5 | 2.18 | 3.18 | 3 | 0 | 1.37 | 2.0 | 0 | 3.23 |
| human 0.1 | GPT-5.2 | 6.73 | 5.79 | 3 | 0 | 2.33 | 2.0 | 0 | 2.91 |
| human 0.1 | Sonnet 4 | 5.54 | 2.68 | 3 | 0 | 4.13 | 2.0 | 0 | 2.81 |
| human 0.1 | Sonnet 4.5 | 8.87 | 2.68 | 2 | 0 | 6.62 | 2.0 | 0 | 2.85 |
| human 0.1 | Gemini 3 Pro | 4.88 | 2.95 | 1 | 0 | 3.32 | 2.0 | 0 | 3.4 |
| human 0.1 | Kimi K2 | 8.16 | 5.9 | 2 | 0 | 2.77 | 2.0 | 0 | 4.33 |
| human 0.1 | Qwen3 Coder† | 7.4 | 3.42 | 3 | 0 | 5.0 | 2.31 | 0 | 3.5 |
| human 0.3 | GPT-5 | 4.71 | 6.86 | 1 | 0 | 1.37 | 2.0 | 0 | 8.28 |
| human 0.3 | GPT-5.2 |  |  | 0 | 0 | 2.33 | 2.0 | 0 | 5.74 |
| human 0.3 | Sonnet 4 | 10.29 | 4.98 | 1 | 0 | 5.0 | 2.42 | 0 | 5.46 |
| human 0.3 | Sonnet 4.5 | 18.11 | 5.47 | 1 | 0 | 10.0 | 3.02 | 0 | 5.82 |
| human 0.3 | Gemini 3 Pro | 10.16 | 6.13 | 1 | 0 | 5.0 | 3.02 | 0 | 7.38 |
| human 0.3 | Kimi K2 | 14.88 | 10.76 | 1 | 0 | 6.92 | 5.0 | 0 | 10.51 |
| human 0.3 | Qwen3 Coder† | 22.82 | 10.56 | 2 | 0 | 10.0 | 4.63 | 0 | 7.37 |
| human 0.5 | GPT-5 |  |  | 0 | 0 | 13.73 | 20.0 | 0 |  |
| human 0.5 | GPT-5.2 |  |  | 0 | 0 | 10.0 | 8.6 | 0 | 55.5 |
| human 0.5 | Sonnet 4 |  |  | 0 | 0 | 10.33 | 5.0 | 0 | 63.1 |
| human 0.5 | Sonnet 4.5 |  |  | 0 | 0 | 33.08 | 10.0 | 0 |  |
| human 0.5 | Gemini 3 Pro |  |  | 0 | 0 | 16.58 | 10.0 | 0 |  |
| human 0.5 | Kimi K2 |  |  | 0 | 0 | 27.66 | 20.0 | 0 |  |
| human 0.5 | Qwen3 Coder† |  |  | 0 | 0 | 50.0 | 23.14 | 0 |  |

* exploratory, not registered.

## Automated first break-evens

$/h 1.74 to 7.08 (median 4.51); multiples 2.14 to 3.83 (median 2.54)

## The cap's margin at the table rates

| regime | configuration | $/h | multiple | cap margin | low | high | iii chose | iii minus escalate* | escalate* |
|---|---|---|---|---|---|---|---|---|---|
| automated | GPT-5 | 25 | 36.4 | -0.103 | -0.381 | 0.009 | 4x@80, 4x@85, 4x@none | -5.95 | 12.56 |
| automated | GPT-5 | 100 | 145.7 | -0.406 | -1.618 | 0.007 | 4x@80, 4x@85, 4x@none | -26.58 | 50.22 |
| automated | GPT-5 | 300 | 437.0 | -1.212 | -4.839 | 0.007 | 4x@80, 4x@85, 4x@none | -81.6 | 150.67 |
| automated | GPT-5.2 | 25 | 21.5 | -0.009 | -0.084 | 0.023 | 1x@175, 2x@125, 2x@175 | -5.43 | 11.96 |
| automated | GPT-5.2 | 100 | 86.0 | 0.011 | -0.43 | 0.091 | 2x@175, 3x@175, 4x@125 | -25.2 | 47.84 |
| automated | GPT-5.2 | 300 | 258.0 | 0.019 | -1.504 | 0.063 | 4x@125 | -79.63 | 143.53 |
| automated | Sonnet 4 | 25 | 12.1 | -0.004 | -0.06 | 0.003 | 2x@200, 2x@275 | -5.45 | 12.58 |
| automated | Sonnet 4 | 100 | 48.4 | -0.008 | -0.319 | 0.0 | 4x@200, 4x@275 | -28.54 | 50.31 |
| automated | Sonnet 4 | 300 | 145.2 | -0.008 | -0.729 | 0.0 | 4x@200, 4x@275 | -90.66 | 150.93 |
| automated | Sonnet 4.5 | 25 | 7.6 | -0.0 | -0.031 | 0.006 | 2x@175, 2x@225 | -4.37 | 12.56 |
| automated | Sonnet 4.5 | 100 | 30.2 | -0.236 | -0.36 | 0.015 | 4x@150, 4x@175 | -26.1 | 50.22 |
| automated | Sonnet 4.5 | 300 | 90.7 | -0.636 | -1.266 | 0.015 | 4x@150, 4x@175 | -86.02 | 150.67 |
| automated | Gemini 3 Pro | 25 | 15.1 | -0.003 | -0.1 | 0.008 | 2x@300, 2x@400 | -4.86 | 12.29 |
| automated | Gemini 3 Pro | 100 | 60.3 | -0.114 | -0.478 | 0.051 | 4x@175, 4x@225 | -25.03 | 49.17 |
| automated | Gemini 3 Pro | 300 | 181.0 | -0.358 | -1.451 | 0.047 | 4x@175, 4x@225 | -79.51 | 147.51 |
| automated | Kimi K2 | 25 | 18.1 | -0.026 | -0.226 | 0.134 | 2x@175, 2x@250, 2x@275 | -4.75 | 12.62 |
| automated | Kimi K2 | 100 | 72.3 | -0.436 | -1.497 | 0.205 | 4x@175, 4x@250 | -24.79 | 50.48 |
| automated | Kimi K2 | 300 | 216.9 | -1.438 | -5.466 | 0.154 | 4x@175, 4x@250 | -79.22 | 151.43 |
| automated | Qwen3 Coder† | 25 | 11.6 | -0.041 | -0.524 | 0.116 | 2x@175, 2x@225, 2x@300 | -4.67 | 12.56 |
| automated | Qwen3 Coder† | 100 | 46.3 | -0.744 | -1.581 | 0.374 | 4x@125, 4x@225 | -25.93 | 50.22 |
| automated | Qwen3 Coder† | 300 | 138.8 | -2.344 | -4.76 | 0.245 | 4x@125, 4x@225 | -84.22 | 150.67 |
| human 0.5 | GPT-5 | 25 | 36.4 | 0.996 | -0.236 | 1.912 | 1x@5 | 0.04 | 12.56 |
| human 0.5 | GPT-5 | 100 | 145.7 | 2.162 | -1.534 | 6.204 | 1x@20, 1x@35, 2x@20 | 0.75 | 50.22 |
| human 0.5 | GPT-5 | 300 | 437.0 | 5.481 | -4.885 | 17.848 | 1x@20, 1x@35, 2x@20, 4x@20 | 2.43 | 150.67 |
| human 0.5 | GPT-5.2 | 25 | 21.5 | 0.404 | -0.439 | 1.221 | 1x@45, 1x@70 | 0.05 | 11.96 |
| human 0.5 | GPT-5.2 | 100 | 86.0 | 0.747 | -2.021 | 4.032 | 1x@45, 1x@70, 1x@75 | -1.14 | 47.84 |
| human 0.5 | GPT-5.2 | 300 | 258.0 | 1.537 | -6.577 | 11.087 | 1x@45, 1x@50, 1x@70, 1x@75 | -4.18 | 143.53 |
| human 0.5 | Sonnet 4 | 25 | 12.1 | 0.99 | -0.503 | 1.94 | 1x@5 | 0.05 | 12.58 |
| human 0.5 | Sonnet 4 | 100 | 48.4 | 1.447 | -3.129 | 3.924 | 1x@60, 1x@65, 1x@70 | -1.13 | 50.31 |
| human 0.5 | Sonnet 4 | 300 | 145.2 | 3.897 | -10.555 | 10.936 | 1x@60, 1x@70 | -5.52 | 150.93 |
| human 0.5 | Sonnet 4.5 | 25 | 7.6 | 1.94 | 1.063 | 2.841 | 1x@5 | 0.06 | 12.56 |
| human 0.5 | Sonnet 4.5 | 100 | 30.2 | 1.845 | -1.865 | 5.593 | 1x@5, 1x@70, 1x@75 | 0.62 | 50.22 |
| human 0.5 | Sonnet 4.5 | 300 | 90.7 | 4.222 | -5.929 | 15.124 | 1x@70, 1x@75, 1x@90 | -0.49 | 150.67 |
| human 0.5 | Gemini 3 Pro | 25 | 15.1 | 1.311 | -0.125 | 2.438 | 1x@5 | 0.09 | 12.29 |
| human 0.5 | Gemini 3 Pro | 100 | 60.3 | 1.645 | -2.356 | 6.414 | 1x@5, 1x@60 | 0.88 | 49.17 |
| human 0.5 | Gemini 3 Pro | 300 | 181.0 | 2.409 | -8.182 | 15.894 | 1x@5, 1x@70 | 3.12 | 147.51 |
| human 0.5 | Kimi K2 | 25 | 18.1 | 1.778 | 0.235 | 2.841 | 1x@5 | 0.02 | 12.62 |
| human 0.5 | Kimi K2 | 100 | 72.3 | 3.305 | -1.485 | 7.84 | 1x@40, 1x@55, 1x@60, 1x@65 | 0.78 | 50.48 |
| human 0.5 | Kimi K2 | 300 | 216.9 | 8.185 | -5.773 | 21.691 | 1x@40, 1x@55, 1x@65, 3x@40 | 1.99 | 151.43 |
| human 0.5 | Qwen3 Coder† | 25 | 11.6 | 1.753 | 0.663 | 2.704 | 1x@5 | 0.02 | 12.56 |
| human 0.5 | Qwen3 Coder† | 100 | 46.3 | 3.563 | -0.363 | 6.026 | 1x@60, 1x@65 | -1.03 | 50.22 |
| human 0.5 | Qwen3 Coder† | 300 | 138.8 | 10.149 | -2.156 | 16.878 | 1x@65 | -5.61 | 150.67 |

* exploratory: every task sent straight to the outside option.

## Review at 0.5 H: best capped policy against escalating everything*

value_iii / value_escalate 0.963 to 1.035 (median 1.007); value_ii / value_escalate 0.982 to 1.745 (median 1.061)

## Schedules, the state rule and the transfer

| regime | $/h | schedule margin | state margin | transfer margin | iv-t minus ii |
|---|---|---|---|---|---|
| automated | 25 | -0.001 to 0.009 (median 0.000) | 0.002 to 0.094 (median 0.006) | 0.001 to 0.094 (median 0.011) | -0.015 to 0.002 (median 0.000) |
| automated | 100 | -0.098 to 0.189 (median 0.000) | -0.011 to 0.744 (median 0.118) | -0.011 to 0.744 (median 0.118) | 0.000 to 0.000 (median 0.000) |
| automated | 300 | -0.075 to 0.601 (median 0.000) | -0.019 to 1.743 (median 0.362) | -0.019 to 1.743 (median 0.362) | 0.000 to 0.000 (median 0.000) |
| human 0.5 | 25 | 0.000 to 0.000 (median 0.000) | -0.824 to 0.267 (median -0.283) | -0.946 to -0.204 (median -0.474) | -1.465 to -0.027 (median -0.787) |
| human 0.5 | 100 | 0.000 to 0.000 (median 0.000) | -2.871 to 1.200 (median -1.471) | -3.329 to -0.747 (median -1.777) | -0.574 to 0.330 (median 0.000) |
| human 0.5 | 300 | 0.000 to 0.000 (median 0.000) | -9.216 to 3.336 (median -2.409) | -9.954 to -1.537 (median -4.204) | -0.637 to 0.087 (median -0.018) |

## Fitted margins with intervals, automated verifier

| configuration | $/h | transfer | low | high | state | state low | state high | schedule | sched low | sched high |
|---|---|---|---|---|---|---|---|---|---|---|
| GPT-5 | 25 | 0.094 | -0.005 | 0.248 | 0.094 | -0.005 | 0.248 | 0.009 | -0.118 | 0.181 |
| GPT-5 | 100 | 0.378 | 0.071 | 1.609 | 0.378 | 0.071 | 1.609 | 0.028 | -0.905 | 0.598 |
| GPT-5 | 300 | 1.134 | 0.222 | 4.816 | 1.134 | 0.222 | 4.816 | 0.079 | -2.715 | 1.767 |
| GPT-5.2 | 25 | 0.011 | -0.052 | 0.108 | 0.006 | -0.053 | 0.08 | 0.0 | -0.074 | 0.067 |
| GPT-5.2 | 100 | -0.011 | -0.054 | 0.45 | -0.011 | -0.054 | 0.45 | 0.0 | -0.273 | 0.074 |
| GPT-5.2 | 300 | -0.019 | -0.097 | 1.519 | -0.019 | -0.097 | 1.519 | 0.0 | -0.248 | 0.089 |
| Sonnet 4 | 25 | 0.003 | -0.11 | 0.075 | 0.003 | -0.109 | 0.074 | 0.001 | -0.062 | 0.113 |
| Sonnet 4 | 100 | 0.106 | -0.003 | 0.316 | 0.106 | -0.003 | 0.316 | -0.098 | -0.235 | 0.169 |
| Sonnet 4 | 300 | 0.083 | 0.015 | 0.734 | 0.083 | 0.015 | 0.734 | -0.075 | -0.5 | 0.285 |
| Sonnet 4.5 | 25 | 0.001 | -0.114 | 0.147 | 0.002 | -0.114 | 0.147 | -0.001 | -0.135 | 0.115 |
| Sonnet 4.5 | 100 | 0.046 | -0.025 | 0.655 | 0.046 | -0.025 | 0.655 | 0.189 | -0.591 | 0.302 |
| Sonnet 4.5 | 300 | 0.146 | -0.018 | 2.488 | 0.146 | -0.018 | 2.488 | 0.489 | -2.011 | 0.978 |
| Gemini 3 Pro | 25 | 0.001 | -0.095 | 0.081 | 0.004 | -0.092 | 0.083 | 0.0 | -0.029 | 0.128 |
| Gemini 3 Pro | 100 | 0.118 | -0.036 | 0.597 | 0.118 | -0.036 | 0.597 | -0.004 | -0.193 | 0.202 |
| Gemini 3 Pro | 300 | 0.362 | -0.033 | 2.678 | 0.362 | -0.033 | 2.678 | -0.004 | -0.785 | 0.903 |
| Kimi K2 | 25 | 0.026 | -0.11 | 0.136 | 0.043 | -0.115 | 0.136 | 0.0 | -0.034 | 0.142 |
| Kimi K2 | 100 | 0.453 | -0.271 | 1.394 | 0.453 | -0.271 | 1.394 | -0.017 | -0.201 | 0.147 |
| Kimi K2 | 300 | 1.438 | -0.105 | 4.318 | 1.438 | -0.105 | 4.318 | 0.0 | -0.358 | 0.468 |
| Qwen3 Coder† | 25 | 0.056 | -0.092 | 0.534 | 0.055 | -0.07 | 0.544 | 0.0 | -0.251 | 0.165 |
| Qwen3 Coder† | 100 | 0.744 | -0.255 | 1.742 | 0.744 | -0.255 | 1.742 | 0.0 | -0.276 | 0.315 |
| Qwen3 Coder† | 300 | 1.743 | -0.23 | 4.757 | 1.743 | -0.23 | 4.757 | 0.601 | -0.677 | 0.808 |

## Switching configurations

| regime_name | rate | tasks | value_escalate | value_best_single | value_cascade | switch_margin | switch_margin_low | switch_margin_high | best_own | best_own_name | switch % |
|---|---|---|---|---|---|---|---|---|---|---|---|
| automated | 5.0 | 275 | 2.503 | 1.73 | 1.73 | 0.0 |  |  | 1.73 | GPT-5 | 0.0 |
| automated | 10.0 | 275 | 5.005 | 2.969 | 2.969 | 0.0 |  |  | 2.969 | GPT-5 | 0.0 |
| automated | 25.0 | 275 | 12.514 | 6.422 | 5.983 | 0.44 | -0.266 | 1.356 | 6.422 | GPT-5 | 6.8 |
| automated | 50.0 | 275 | 25.027 | 12.179 | 10.835 | 1.344 |  |  | 11.599 | Sonnet 4 | 11.0 |
| automated | 75.0 | 275 | 37.541 | 18.086 | 15.487 | 2.599 |  |  | 16.296 | Sonnet 4 | 14.4 |
| automated | 100.0 | 275 | 50.055 | 21.97 | 19.944 | 2.025 | -2.224 | 5.593 | 20.992 | Sonnet 4 | 9.2 |
| automated | 150.0 | 275 | 75.082 | 31.817 | 28.862 | 2.955 |  |  | 30.385 | Sonnet 4 | 9.3 |
| automated | 200.0 | 275 | 100.109 | 41.664 | 37.929 | 3.735 |  |  | 39.777 | Sonnet 4 | 9.0 |
| automated | 300.0 | 275 | 150.164 | 61.359 | 56.01 | 5.349 | -8.298 | 17.953 | 58.563 | Sonnet 4 | 8.7 |
| human 0.1 | 5.0 | 275 | 2.503 | 1.992 | 1.992 | 0.0 |  |  | 1.992 | GPT-5 | 0.0 |
| human 0.1 | 10.0 | 275 | 5.005 | 3.648 | 3.648 | 0.0 |  |  | 3.589 | GPT-5 | 0.0 |
| human 0.1 | 25.0 | 275 | 12.514 | 7.93 | 7.969 | -0.039 |  |  | 7.93 | GPT-5.2 | -0.5 |
| human 0.1 | 50.0 | 275 | 25.027 | 15.14 | 14.863 | 0.276 |  |  | 15.14 | GPT-5.2 | 1.8 |
| human 0.1 | 75.0 | 275 | 37.541 | 22.349 | 21.605 | 0.744 |  |  | 22.349 | GPT-5.2 | 3.3 |
| human 0.1 | 100.0 | 275 | 50.055 | 30.295 | 28.347 | 1.948 |  |  | 29.558 | GPT-5.2 | 6.4 |
| human 0.1 | 150.0 | 275 | 75.082 | 45.317 | 41.721 | 3.596 |  |  | 43.977 | GPT-5.2 | 7.9 |
| human 0.1 | 200.0 | 275 | 100.109 | 60.699 | 55.223 | 5.476 |  |  | 58.396 | GPT-5.2 | 9.0 |
| human 0.1 | 300.0 | 275 | 150.164 | 90.734 | 82.259 | 8.475 |  |  | 87.233 | GPT-5.2 | 9.3 |
| human 0.3 | 5.0 | 275 | 2.503 | 2.491 | 2.491 | 0.0 |  |  | 2.491 | GPT-5 | 0.0 |
| human 0.3 | 10.0 | 275 | 5.005 | 4.677 | 4.677 | 0.0 |  |  | 4.589 | GPT-5 | 0.0 |
| human 0.3 | 25.0 | 275 | 12.514 | 10.316 | 10.316 | 0.0 |  |  | 10.316 | GPT-5.2 | 0.0 |
| human 0.3 | 50.0 | 275 | 25.027 | 19.939 | 19.939 | 0.0 |  |  | 19.939 | GPT-5.2 | 0.0 |
| human 0.3 | 75.0 | 275 | 37.541 | 29.563 | 29.563 | 0.0 |  |  | 29.563 | GPT-5.2 | 0.0 |
| human 0.3 | 100.0 | 275 | 50.055 | 39.186 | 39.186 | 0.0 |  |  | 39.186 | GPT-5.2 | 0.0 |
| human 0.3 | 150.0 | 275 | 75.082 | 58.433 | 58.433 | 0.0 |  |  | 58.433 | GPT-5.2 | 0.0 |
| human 0.3 | 200.0 | 275 | 100.109 | 77.679 | 77.865 | -0.185 |  |  | 77.679 | GPT-5.2 | -0.2 |
| human 0.3 | 300.0 | 275 | 150.164 | 116.173 | 116.432 | -0.259 |  |  | 116.173 | GPT-5.2 | -0.2 |
| human 0.5 | 5.0 | 275 | 2.503 | 2.521 | 2.521 | 0.0 |  |  | 2.521 | Kimi K2 | 0.0 |
| human 0.5 | 10.0 | 275 | 5.005 | 5.023 | 5.023 | 0.0 |  |  | 5.023 | Kimi K2 | 0.0 |
| human 0.5 | 25.0 | 275 | 12.514 | 12.883 | 12.883 | 0.0 |  |  | 12.535 | Qwen3 Coder† | 0.0 |
| human 0.5 | 50.0 | 275 | 25.027 | 24.721 | 24.721 | 0.0 |  |  | 24.721 | GPT-5.2 | 0.0 |
| human 0.5 | 75.0 | 275 | 37.541 | 36.777 | 36.777 | 0.0 |  |  | 36.777 | GPT-5.2 | 0.0 |
| human 0.5 | 100.0 | 275 | 50.055 | 48.843 | 48.843 | 0.0 |  |  | 48.843 | GPT-5.2 | 0.0 |
| human 0.5 | 150.0 | 275 | 75.082 | 72.975 | 72.975 | 0.0 |  |  | 72.975 | GPT-5.2 | 0.0 |
| human 0.5 | 200.0 | 275 | 100.109 | 97.158 | 97.158 | 0.0 |  |  | 97.158 | GPT-5.2 | 0.0 |
| human 0.5 | 300.0 | 275 | 150.164 | 145.444 | 146.445 | -1.0 |  |  | 145.444 | GPT-5.2 | -0.7 |

## Each configuration's own schedule on the common tasks

| regime | rate | Sonnet 4.5 | Sonnet 4 | Gemini 3 Pro | GPT-5 | GPT-5.2 | Kimi K2 | Qwen3 Coder† | spread |
|---|---|---|---|---|---|---|---|---|---|
| automated | 25.0 | 8.05 | 7.09 | 7.38 | 6.42 | 6.7 | 7.87 | 7.23 | 1.62 |
| automated | 100.0 | 24.56 | 20.99 | 24.54 | 23.18 | 23.11 | 26.26 | 22.48 | 5.26 |
| automated | 300.0 | 66.4 | 58.56 | 69.36 | 67.85 | 65.46 | 74.13 | 62.23 | 15.57 |
| human 0.1 | 25.0 | 9.35 | 8.46 | 8.85 | 8.38 | 7.93 | 9.41 | 8.8 | 1.48 |
| human 0.1 | 100.0 | 32.54 | 30.57 | 32.83 | 32.98 | 29.56 | 35.59 | 31.07 | 6.03 |
| human 0.1 | 300.0 | 94.22 | 87.34 | 97.06 | 97.97 | 87.23 | 103.22 | 87.53 | 15.99 |
| human 0.3 | 25.0 | 11.92 | 10.96 | 11.63 | 10.8 | 10.32 | 11.58 | 11.34 | 1.61 |
| human 0.3 | 100.0 | 42.28 | 40.26 | 42.22 | 42.02 | 39.19 | 44.58 | 41.05 | 5.4 |
| human 0.3 | 300.0 | 123.35 | 118.4 | 124.71 | 125.28 | 116.17 | 133.0 | 120.47 | 16.83 |
| human 0.5 | 25.0 | 12.57 | 12.87 | 12.6 | 12.81 | 12.72 | 12.8 | 12.53 | 0.34 |
| human 0.5 | 100.0 | 51.03 | 49.74 | 50.68 | 51.8 | 48.84 | 50.61 | 49.34 | 2.96 |
| human 0.5 | 300.0 | 148.64 | 147.23 | 150.86 | 154.43 | 145.44 | 150.38 | 146.25 | 8.99 |

Cross-fitted, on the cascade's common tasks; spread is the dearest minus the cheapest.

## The ladder's span within a configuration, own tasks

| regime | $/h | i minus the best of ii to iii-b |
|---|---|---|
| automated | 25 | -0.06 to 1.04 (median 0.21) |
| automated | 100 | 1.02 to 5.67 (median 3.83) |
| automated | 300 | 5.60 to 18.04 (median 15.47) |
| human 0.5 | 25 | 0.40 to 1.94 (median 1.31) |
| human 0.5 | 100 | 0.75 to 3.56 (median 1.85) |
| human 0.5 | 300 | 1.54 to 10.15 (median 4.22) |

## Leave-one-out essentialness

| regime | rate | Sonnet 4.5 | Sonnet 4 | Gemini 3 Pro | GPT-5 | GPT-5.2 | Kimi K2 | Qwen3 Coder† |
|---|---|---|---|---|---|---|---|---|
| automated | 25.0 | 0.0 | 0.309 | 0.0 | 0.407 | 0.032 | 0.0 | 0.0 |
| automated | 100.0 | -0.062 | 0.963 | -0.152 | 0.0 | 1.483 | 0.0 | 0.0 |
| automated | 300.0 | -0.222 | 2.045 | 0.0 | 0.0 | 2.191 | 0.0 | 0.0 |
| human 0.5 | 25.0 | 0.0 | 0.0 | 0.0 | 0.0 | -0.08 | 0.001 | 0.0 |
| human 0.5 | 100.0 | 0.0 | 0.0 | 0.0 | 0.0 | 1.124 | 0.0 | 0.0 |
| human 0.5 | 300.0 | 0.0 | -1.0 | 0.0 | 0.0 | 2.704 | 0.0 | 0.0 |

## Outcome correlation

off-diagonal 0.62 to 0.90 (median 0.81)

## Break-evens under each sensitivity

| variant | regime | cross | first crossing x | supported |
|---|---|---|---|---|
| primary | automated | 7 of 7 | 2.14 to 3.83 (median 2.54) | 0 |
| primary | human 0.1 | 7 of 7 | 2.68 to 5.90 (median 3.18) | 0 |
| primary | human 0.3 | 6 of 7 | 4.98 to 10.76 (median 6.49) | 0 |
| primary | human 0.5 | 0 of 7 | n/a | 0 |
| phi 0.34 | automated | 7 of 7 | 3.24 to 5.79 (median 3.83) | 0 |
| phi 0.34 | human 0.1 | 6 of 7 | 4.62 to 12.50 (median 5.38) | 0 |
| phi 0.34 | human 0.3 | 2 of 7 | 29.65 to 46.53 (median 38.09) | 0 |
| phi 0.34 | human 0.5 | 0 of 7 | n/a | 0 |
| phi 0.50 | automated | 7 of 7 | 4.29 to 7.68 (median 4.98) | 0 |
| phi 0.50 | human 0.1 | 7 of 7 | 6.99 to 12.50 (median 7.97) | 0 |
| phi 0.50 | human 0.3 | 0 of 7 | n/a | 0 |
| phi 0.50 | human 0.5 | 0 of 7 | n/a | 0 |
| common horizon 100 | automated | 7 of 7 | 2.54 to 3.30 (median 2.73) | 2 |
| common horizon 100 | human 0.1 | 7 of 7 | 2.68 to 4.13 (median 3.30) | 2 |
| common horizon 100 | human 0.3 | 7 of 7 | 4.62 to 53.06 (median 6.73) | 0 |
| common horizon 100 | human 0.5 | 2 of 7 | 40.80 to 58.28 (median 49.54) | 0 |
| all tasks | automated | 7 of 7 | 2.14 to 4.29 (median 2.49) | 0 |
| all tasks | human 0.1 | 7 of 7 | 2.68 to 7.12 (median 3.06) | 0 |
| all tasks | human 0.3 | 7 of 7 | 5.08 to 17.86 (median 6.13) | 0 |
| all tasks | human 0.5 | 2 of 7 | 45.66 to 135.64 (median 90.65) | 0 |
| refusals excluded | automated | 7 of 7 | 2.14 to 3.83 (median 2.44) | 0 |
| refusals excluded | human 0.1 | 7 of 7 | 2.68 to 5.90 (median 3.12) | 0 |
| refusals excluded | human 0.3 | 6 of 7 | 4.98 to 10.76 (median 6.43) | 0 |
| refusals excluded | human 0.5 | 0 of 7 | n/a | 0 |
| no verdict unresolved | automated | 7 of 7 | 2.14 to 6.48 (median 2.54) | 0 |
| no verdict unresolved | human 0.1 | 7 of 7 | 2.68 to 6.61 (median 3.18) | 0 |
| no verdict unresolved | human 0.3 | 6 of 7 | 4.98 to 10.76 (median 6.49) | 0 |
| no verdict unresolved | human 0.5 | 0 of 7 | n/a | 0 |
| re-runs dropped | automated | 7 of 7 | 2.14 to 7.82 (median 2.31) | 0 |
| re-runs dropped | human 0.1 | 6 of 7 | 2.63 to 9.98 (median 3.03) | 0 |
| re-runs dropped | human 0.3 | 7 of 7 | 4.80 to 88.08 (median 6.86) | 0 |
| re-runs dropped | human 0.5 | 1 of 7 | 271.66 to 271.66 (median 271.66) | 0 |
| Qwen lowest price | automated | 7 of 7 | 2.14 to 3.83 (median 2.54) | 0 |
| Qwen lowest price | human 0.1 | 7 of 7 | 2.68 to 5.90 (median 3.18) | 0 |
| Qwen lowest price | human 0.3 | 6 of 7 | 4.98 to 10.76 (median 6.49) | 0 |
| Qwen lowest price | human 0.5 | 0 of 7 | n/a | 0 |
| METR minutes | automated | 7 of 7 | 1.84 to 8.75 (median 2.09) | 0 |
| METR minutes | human 0.1 | 7 of 7 | 2.22 to 6.99 (median 2.55) | 0 |
| METR minutes | human 0.3 | 7 of 7 | 3.62 to 12.74 (median 4.53) | 0 |
| METR minutes | human 0.5 | 3 of 7 | 11.60 to 49.22 (median 35.11) | 0 |

## Cells of any sweep where the cap is resolved as a cost

0

## Margins at $100 under each sensitivity

| variant | cap, automated $100 | cap, review 0.5 $100 | transfer, automated $100 |
|---|---|---|---|
| primary | -0.744 to 0.011 (median -0.236) | 0.747 to 3.563 (median 1.845) | -0.011 to 0.744 (median 0.118) |
| phi 0.34 | -0.468 to 0.004 (median -0.072) | 8.022 to 11.566 (median 10.205) | -0.003 to 0.468 (median 0.076) |
| phi 0.50 | -0.435 to 0.003 (median -0.053) | 12.009 to 15.097 (median 13.689) | -0.000 to 0.409 (median 0.072) |
| common horizon 100 | -0.406 to 0.020 (median 0.000) | -0.232 to 2.702 (median 1.074) | 0.000 to 0.378 (median 0.000) |
| all tasks | -0.744 to 0.017 (median -0.236) | -2.003 to 3.718 (median 1.845) | -0.017 to 0.744 (median 0.124) |
| refusals excluded | -0.744 to 0.011 (median -0.236) | 0.747 to 3.563 (median 1.845) | -0.011 to 0.744 (median 0.118) |
| no verdict unresolved | -0.744 to 0.012 (median -0.236) | 0.716 to 3.563 (median 1.845) | -0.012 to 0.744 (median 0.118) |
| re-runs dropped | -0.834 to 0.027 (median -0.248) | 0.154 to 4.092 (median 1.873) | -0.026 to 0.834 (median 0.159) |
| Qwen lowest price | -0.789 to 0.011 (median -0.236) | 0.747 to 3.354 (median 1.845) | -0.011 to 0.589 (median 0.118) |
| METR minutes | -0.600 to 0.019 (median -0.393) | -1.095 to 4.956 (median 0.371) | -0.019 to 0.600 (median 0.302) |

## Common 100-call horizon: what retrying costs at $100, automated

| configuration | value_ii | value_ii_horizon | added |
|---|---|---|---|
| Sonnet 4.5 | 23.89 | 30.83 | 6.94 |
| Sonnet 4 | 21.76 | 23.61 | 1.85 |
| Gemini 3 Pro | 24.03 | 29.0 | 4.98 |
| GPT-5 | 23.23 | 23.23 | 0.0 |
| GPT-5.2 | 22.65 | 22.96 | 0.31 |
| Kimi K2 | 25.26 | 29.86 | 4.61 |
| Qwen3 Coder† | 23.55 | 26.38 | 2.83 |

added is the common horizon minus the primary, own tasks.

## Switching at $100, automated, under each sensitivity

| variant | tasks | value_best_single | value_cascade | switch_margin |
|---|---|---|---|---|
| primary | 275 | 21.97 | 19.944 | 2.025 |
| phi 0.34 | 275 | 32.498 | 30.84 | 1.658 |
| phi 0.50 | 275 | 37.206 | 35.862 | 1.344 |
| common horizon 100 | 275 | 25.326 | 20.905 | 4.421 |
| all tasks | 499 | 24.421 | 20.025 | 4.395 |
| refusals excluded | 238 | 25.011 | 20.914 | 4.097 |
| no verdict unresolved | 277 | 21.822 | 19.815 | 2.007 |
| re-runs dropped | 146 | 20.932 | 19.936 | 0.996 |
| Qwen lowest price | 275 | 22.035 | 20.108 | 1.927 |
| METR minutes | 275 | 36.193 | 30.718 | 5.475 |

## Two-stage bootstrap

cap cells 532; width ratio two/one 0.45 to 1.73 (median 1.02); cells where two-stage excludes zero but one-stage does not: -1 net; centre shift -0.748 to 1.968 (median -0.000)

## Two-stage transfer

| config | rate | estimate | two_stage_low | two_stage_high |
|---|---|---|---|---|
| claude-sonnet-4.5_4runs | 25.0 | 0.001 | -0.004 | 0.059 |
| claude-sonnet-4.5_4runs | 100.0 | 0.046 | -0.016 | 0.581 |
| claude-sonnet-4.5_4runs | 300.0 | 0.146 | -0.016 | 1.272 |
| claude-sonnet-4_4runs | 25.0 | 0.003 | -0.01 | 0.082 |
| claude-sonnet-4_4runs | 100.0 | 0.106 | -0.017 | 0.262 |
| claude-sonnet-4_4runs | 300.0 | 0.083 | -0.005 | 0.577 |
| gemini-3-pro-preview_4runs | 25.0 | 0.001 | -0.022 | 0.104 |
| gemini-3-pro-preview_4runs | 100.0 | 0.118 | -0.04 | 0.491 |
| gemini-3-pro-preview_4runs | 300.0 | 0.362 | -0.038 | 1.467 |
| gpt-5_4runs | 25.0 | 0.094 | -0.003 | 0.209 |
| gpt-5_4runs | 100.0 | 0.378 | 0.006 | 0.907 |
| gpt-5_4runs | 300.0 | 1.134 | 0.037 | 2.716 |
| gpt_5.2_4runs | 25.0 | 0.011 | -0.015 | 0.072 |
| gpt_5.2_4runs | 100.0 | -0.011 | -0.053 | 0.369 |
| gpt_5.2_4runs | 300.0 | -0.019 | -0.046 | 1.298 |
| kimi-k2_4runs | 25.0 | 0.026 | -0.184 | 0.246 |
| kimi-k2_4runs | 100.0 | 0.453 | -0.237 | 0.992 |
| kimi-k2_4runs | 300.0 | 1.438 | -0.129 | 2.961 |
| qwen3-coder-480b-a35b-instruct-4runs | 25.0 | 0.056 | -0.084 | 0.457 |
| qwen3-coder-480b-a35b-instruct-4runs | 100.0 | 0.744 | -0.179 | 1.653 |
| qwen3-coder-480b-a35b-instruct-4runs | 300.0 | 1.743 | -0.152 | 4.85 |

## Comparators

| regime | $/h | cap in calls | dollar_cap_margin | rule_vs_threshold | schedule_vs_universal | first_look_margin | state_margin |
|---|---|---|---|---|---|---|---|
| automated | 25 | -0.103 to -0.000 (median -0.009) | -0.062 to 0.010 (median -0.017); resolved 0 of 7 | 0.019 to 0.372 (median 0.081); resolved 1 of 7 | -0.018 to 0.001 (median 0.000); resolved 0 of 7 | 0.001 to 0.094 (median 0.009); resolved 0 of 7 | 0.002 to 0.094 (median 0.006) |
| automated | 100 | -0.744 to 0.011 (median -0.236) | -0.580 to 0.182 (median -0.121); resolved 0 of 7 | 0.246 to 1.166 (median 0.479); resolved 1 of 7 | -0.386 to 0.033 (median -0.075); resolved 0 of 7 | -0.011 to 0.744 (median 0.118); resolved 1 of 7 | -0.011 to 0.744 (median 0.118) |
| automated | 300 | -2.344 to 0.019 (median -0.636) | -1.825 to 0.038 (median -0.365); resolved 0 of 7 | -0.124 to 3.913 (median 2.049); resolved 2 of 7 | -0.585 to 0.033 (median -0.093); resolved 0 of 7 | -0.019 to 1.743 (median 0.362); resolved 2 of 7 | -0.019 to 1.743 (median 0.362) |
| human 0.5 | 25 | 0.404 to 1.940 (median 1.311) | 0.589 to 1.937 (median 1.309) | -0.818 to 0.270 (median -0.269) | 0.000 to 0.003 (median 0.000) | -1.755 to -0.360 (median -1.194) | -0.824 to 0.267 (median -0.283) |
| human 0.5 | 100 | 0.747 to 3.563 (median 1.845) | 1.399 to 4.883 (median 2.124) | -3.134 to 0.569 (median -1.397) | -0.459 to 1.059 (median 0.006) | -3.563 to -0.626 (median -1.845) | -2.871 to 1.200 (median -1.471) |
| human 0.5 | 300 | 1.537 to 10.149 (median 4.222) | 4.183 to 12.043 (median 7.534) | -9.443 to 1.451 (median -3.634) | -2.091 to 3.546 (median -0.130) | -10.149 to -1.232 (median -4.222) | -9.216 to 3.336 (median -2.409) |

## Review 0.5 at $100: the dollar cap saves more than the cap in calls

6 of 7 configurations

## Sample oracle

| regime_name | rate | tasks | value_oracle | value_cascade | value_best_single | oracle_gap | share |
|---|---|---|---|---|---|---|---|
| automated | 25.0 | 275 | 3.99 | 5.98 | 6.42 | 1.99 | 33.3 |
| automated | 100.0 | 275 | 14.07 | 19.94 | 21.97 | 5.87 | 29.4 |
| automated | 300.0 | 275 | 40.9 | 56.01 | 61.36 | 15.11 | 27.0 |
| human 0.1 | 25.0 | 275 | 5.02 | 7.97 | 7.93 | 2.95 | 37.1 |
| human 0.1 | 100.0 | 275 | 18.13 | 28.35 | 30.29 | 10.22 | 36.0 |
| human 0.1 | 300.0 | 275 | 53.01 | 82.26 | 90.73 | 29.25 | 35.6 |
| human 0.3 | 25.0 | 275 | 7.01 | 10.32 | 10.32 | 3.3 | 32.0 |
| human 0.3 | 100.0 | 275 | 26.18 | 39.19 | 39.19 | 13.01 | 33.2 |
| human 0.3 | 300.0 | 275 | 77.17 | 116.43 | 116.17 | 39.26 | 33.7 |
| human 0.5 | 25.0 | 275 | 8.85 | 12.88 | 12.88 | 4.03 | 31.3 |
| human 0.5 | 100.0 | 275 | 33.78 | 48.84 | 48.84 | 15.06 | 30.8 |
| human 0.5 | 300.0 | 275 | 100.16 | 146.44 | 145.44 | 46.29 | 31.6 |

share: gap as % of the cascade.

## Difficulty at $100

| regime | bucket | tasks | cap margin | resolved | value ii | value iii |
|---|---|---|---|---|---|---|
| automated | under 15 minutes | 158 to 194 (median 193) | -0.029 to 0.043 (median -0.014) | 0 of 7 | 1.98 to 3.25 (median 2.35) | 2.00 to 3.27 (median 2.31) |
| automated | 15 minutes to 1 hour | 210 to 261 (median 257) | -0.459 to 0.307 (median -0.002) | 0 of 7 | 15.22 to 19.16 (median 17.44) | 15.22 to 19.04 (median 17.21) |
| automated | 1 to 4 hours | 30 to 42 (median 42) | -9.683 to 0.003 (median -5.209) | 1 of 7 | 111.63 to 127.28 (median 121.85) | 114.53 to 134.08 (median 125.76) |
| automated | over 4 hours | 2 to 3 (median 3) | n/a | 0 of 0 | n/a | n/a |
| automated | 1 hour or more | 32 to 45 (median 45) | -9.035 to 0.003 (median -4.775) | 0 of 7 | 140.15 to 169.48 (median 153.04) | 142.70 to 175.86 (median 155.30) |
| automated | all, chosen within bucket | 405 to 500 (median 496) | -1.058 to -0.003 (median -0.365) | 0 of 0 | 21.71 to 25.13 (median 23.48) | 21.71 to 25.50 (median 24.12) |
| automated | all, chosen blind | 405 to 500 (median 496) | -0.744 to 0.011 (median -0.236) | 0 of 0 | 21.76 to 25.26 (median 23.55) | 21.77 to 25.69 (median 24.12) |
| human 0.5 | under 15 minutes | 158 to 194 (median 193) | -0.133 to 0.163 (median -0.006) | 0 of 7 | 5.39 to 6.50 (median 5.55) | 5.42 to 6.64 (median 5.48) |
| human 0.5 | 15 minutes to 1 hour | 210 to 261 (median 257) | -0.487 to 0.680 (median -0.042) | 0 of 7 | 41.94 to 48.72 (median 45.41) | 42.39 to 48.04 (median 45.49) |
| human 0.5 | 1 to 4 hours | 30 to 42 (median 42) | 26.014 to 44.094 (median 36.301) | 3 of 7 | 231.27 to 249.39 (median 243.45) | 200.02 to 215.98 (median 200.62) |
| human 0.5 | over 4 hours | 2 to 3 (median 3) | n/a | 0 of 0 | n/a | n/a |
| human 0.5 | 1 hour or more | 32 to 45 (median 45) | 38.621 to 62.828 (median 53.967) | 2 of 7 | 282.85 to 306.49 (median 294.03) | 232.51 to 253.24 (median 240.58) |
| human 0.5 | all, chosen within bucket | 405 to 500 (median 496) | 2.813 to 5.681 (median 5.030) | 0 of 0 | 47.45 to 54.56 (median 52.69) | 44.64 to 49.47 (median 47.45) |
| human 0.5 | all, chosen blind | 405 to 500 (median 496) | 0.747 to 3.563 (median 1.845) | 0 of 0 | 47.45 to 54.56 (median 52.69) | 46.70 to 51.25 (median 50.05) |

## Admitting the annotation, $100

| regime | configuration | best of ii, iii within | best of ii, iii blind | cap within | cap blind |
|---|---|---|---|---|---|
| automated | GPT-5 | 23.225 | 23.234 | -0.115 | -0.406 |
| automated | GPT-5.2 | 22.638 | 22.641 | -0.512 | 0.011 |
| automated | Sonnet 4 | 21.706 | 21.763 | -0.003 | -0.008 |
| automated | Sonnet 4.5 | 23.48 | 23.889 | -1.058 | -0.236 |
| automated | Gemini 3 Pro | 24.054 | 24.026 | -0.115 | -0.114 |
| automated | Kimi K2 | 25.133 | 25.255 | -0.365 | -0.436 |
| automated | Qwen3 Coder† | 23.519 | 23.553 | -0.604 | -0.744 |
| human 0.5 | GPT-5 | 47.455 | 50.974 | 5.681 | 2.162 |
| human 0.5 | GPT-5.2 | 44.637 | 46.704 | 2.813 | 0.747 |
| human 0.5 | Sonnet 4 | 47.249 | 49.177 | 3.375 | 1.447 |
| human 0.5 | Sonnet 4.5 | 47.954 | 50.847 | 4.738 | 1.845 |
| human 0.5 | Gemini 3 Pro | 46.665 | 50.05 | 5.03 | 1.645 |
| human 0.5 | Kimi K2 | 49.471 | 51.253 | 5.086 | 3.305 |
| human 0.5 | Qwen3 Coder† | 47.52 | 49.188 | 5.231 | 3.563 |

## Distribution of cost at $100

| regime | p95 ii | p95 iii | cap at p95 | median ii | median iii | median version |
|---|---|---|---|---|---|---|
| automated | 66.87 to 203.31 (median 202.47) | 64.81 to 204.82 (median 202.47) | -1.52 to 2.06 (median 0.00) | 0.50 to 2.06 (median 1.23) | 0.50 to 2.06 (median 1.23) | -0.002 to 0.000 (median 0.000) |
| human 0.1 | 220.40 to 240.43 (median 221.44) | 220.39 to 240.64 (median 221.50) | -0.22 to 3.57 (median 0.00) | 5.44 to 6.85 (median 6.08) | 5.43 to 6.85 (median 6.09) | -0.013 to 0.000 (median -0.002) |
| human 0.3 | 260.40 to 261.73 (median 260.79) | 201.75 to 261.73 (median 260.71) | 0.00 to 58.65 (median 0.01) | 15.29 to 16.48 (median 15.69) | 15.29 to 16.48 (median 15.69) | -0.009 to 0.006 (median 0.000) |
| human 0.5 | 300.40 to 301.77 (median 300.83) | 200.08 to 201.29 (median 200.76) | 99.65 to 100.63 (median 100.37) | 25.29 to 26.48 (median 25.69) | 25.44 to 50.25 (median 50.06) | -0.009 to 0.000 (median -0.000) |

## Spread

| regime_name | rate | tasks | across_best | across_one | within_median | within_max | cheapest | dearest |
|---|---|---|---|---|---|---|---|---|
| automated | 5.0 | 275 | 0.85 | 1.29 | 0.01 | 0.46 | gpt-5_4runs | qwen3-coder-480b-a35b-instruct-4runs |
| automated | 10.0 | 275 | 1.32 | 1.22 | 0.0 | 0.1 | gpt-5_4runs | claude-sonnet-4.5_4runs |
| automated | 25.0 | 275 | 1.76 | 1.47 | 0.24 | 0.78 | gpt-5_4runs | claude-sonnet-4.5_4runs |
| automated | 50.0 | 275 | 2.47 | 2.69 | 1.29 | 2.0 | claude-sonnet-4_4runs | kimi-k2_4runs |
| automated | 75.0 | 275 | 3.7 | 3.92 | 2.57 | 3.22 | claude-sonnet-4_4runs | kimi-k2_4runs |
| automated | 100.0 | 275 | 4.94 | 5.15 | 3.83 | 4.44 | claude-sonnet-4_4runs | kimi-k2_4runs |
| automated | 150.0 | 275 | 6.89 | 7.6 | 6.76 | 6.98 | claude-sonnet-4_4runs | kimi-k2_4runs |
| automated | 200.0 | 275 | 9.17 | 10.05 | 9.33 | 9.64 | claude-sonnet-4_4runs | kimi-k2_4runs |
| automated | 300.0 | 275 | 13.72 | 14.96 | 14.22 | 15.08 | claude-sonnet-4_4runs | kimi-k2_4runs |
| human 0.1 | 5.0 | 275 | 0.59 | 1.29 | 0.1 | 0.71 | gpt-5_4runs | claude-sonnet-4.5_4runs |
| human 0.1 | 10.0 | 275 | 1.23 | 1.23 | 0.01 | 0.04 | gpt-5_4runs | claude-sonnet-4.5_4runs |
| human 0.1 | 25.0 | 275 | 1.47 | 1.47 | 0.01 | 0.09 | gpt_5.2_4runs | kimi-k2_4runs |
| human 0.1 | 50.0 | 275 | 2.69 | 2.69 | 0.02 | 0.55 | gpt_5.2_4runs | kimi-k2_4runs |
| human 0.1 | 75.0 | 275 | 3.91 | 3.91 | 0.26 | 0.78 | gpt_5.2_4runs | kimi-k2_4runs |
| human 0.1 | 100.0 | 275 | 5.14 | 5.14 | 0.41 | 1.01 | gpt_5.2_4runs | kimi-k2_4runs |
| human 0.1 | 150.0 | 275 | 7.59 | 7.59 | 0.74 | 1.47 | gpt_5.2_4runs | kimi-k2_4runs |
| human 0.1 | 200.0 | 275 | 10.04 | 10.04 | 1.24 | 1.93 | gpt_5.2_4runs | kimi-k2_4runs |
| human 0.1 | 300.0 | 275 | 14.96 | 14.93 | 1.64 | 2.86 | claude-sonnet-4_4runs | kimi-k2_4runs |
| human 0.3 | 5.0 | 275 | 0.15 | 1.3 | 0.59 | 1.21 | gpt-5_4runs | gpt_5.2_4runs |
| human 0.3 | 10.0 | 275 | 0.59 | 1.26 | 0.15 | 0.72 | gpt-5_4runs | kimi-k2_4runs |
| human 0.3 | 25.0 | 275 | 1.53 | 1.46 | 0.1 | 0.35 | gpt_5.2_4runs | claude-sonnet-4.5_4runs |
| human 0.3 | 50.0 | 275 | 2.53 | 2.68 | 0.09 | 0.32 | gpt_5.2_4runs | kimi-k2_4runs |
| human 0.3 | 75.0 | 275 | 3.83 | 3.9 | 0.14 | 0.31 | gpt_5.2_4runs | kimi-k2_4runs |
| human 0.3 | 100.0 | 275 | 5.4 | 5.12 | 0.15 | 0.31 | gpt_5.2_4runs | kimi-k2_4runs |
| human 0.3 | 150.0 | 275 | 8.02 | 7.56 | 0.29 | 0.46 | gpt_5.2_4runs | kimi-k2_4runs |
| human 0.3 | 200.0 | 275 | 10.6 | 10.0 | 0.39 | 0.64 | gpt_5.2_4runs | kimi-k2_4runs |
| human 0.3 | 300.0 | 275 | 15.76 | 14.88 | 0.58 | 1.07 | gpt_5.2_4runs | kimi-k2_4runs |
| human 0.5 | 5.0 | 275 | 0.07 | 1.32 | 1.09 | 1.71 | kimi-k2_4runs | gemini-3-pro-preview_4runs |
| human 0.5 | 10.0 | 275 | 0.07 | 1.28 | 1.04 | 1.72 | kimi-k2_4runs | gemini-3-pro-preview_4runs |
| human 0.5 | 25.0 | 275 | 0.34 | 1.46 | 1.13 | 1.77 | qwen3-coder-480b-a35b-instruct-4runs | claude-sonnet-4_4runs |
| human 0.5 | 50.0 | 275 | 1.14 | 2.67 | 0.53 | 2.1 | gpt_5.2_4runs | gpt-5_4runs |
| human 0.5 | 75.0 | 275 | 1.97 | 3.89 | 0.86 | 3.13 | gpt_5.2_4runs | gpt-5_4runs |
| human 0.5 | 100.0 | 275 | 2.69 | 5.1 | 1.1 | 3.98 | gpt_5.2_4runs | gpt-5_4runs |
| human 0.5 | 150.0 | 275 | 4.13 | 7.54 | 1.74 | 5.75 | gpt_5.2_4runs | gpt-5_4runs |
| human 0.5 | 200.0 | 275 | 5.52 | 9.97 | 2.19 | 7.51 | gpt_5.2_4runs | gpt-5_4runs |
| human 0.5 | 300.0 | 275 | 8.37 | 14.83 | 3.09 | 11.44 | gpt_5.2_4runs | gpt-5_4runs |

## Diagnostics

| quantity | range |
|---|---|
| within_task_share | 0.245 to 0.642 (median 0.295) |
| mixed_share | 0.114 to 0.245 (median 0.224) |
| all_fail_share | 0.223 to 0.311 (median 0.284) |
| all_resolve_share | 0.444 to 0.607 (median 0.528) |
| resolve_rate | 0.580 to 0.688 (median 0.641) |
| over_outside_25 | 0.001 to 0.145 (median 0.038) |
| over_outside_100 | 0.000 to 0.003 (median 0.000) |
