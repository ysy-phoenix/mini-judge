## Test Settings

```bash
Architecture:                       x86_64
CPU op-mode(s):                     32-bit, 64-bit
Byte Order:                         Little Endian
Address sizes:                      48 bits physical, 48 bits virtual
CPU(s):                             64
On-line CPU(s) list:                0-63
Thread(s) per core:                 2
Core(s) per socket:                 32
Socket(s):                          1
NUMA node(s):                       1
Vendor ID:                          AuthenticAMD
CPU family:                         25
Model:                              1
Model name:                         AMD EPYC 7763 64-Core Processor
Stepping:                           1
CPU MHz:                            2445.427
BogoMIPS:                           4890.85
Virtualization:                     AMD-V
Hypervisor vendor:                  Microsoft
Virtualization type:                full
L1d cache:                          1 MiB
L1i cache:                          1 MiB
L2 cache:                           16 MiB
L3 cache:                           128 MiB
NUMA node0 CPU(s):                  0-63
Vulnerability Gather data sampling: Not affected
Vulnerability Itlb multihit:        Not affected
Vulnerability L1tf:                 Not affected
Vulnerability Mds:                  Not affected
Vulnerability Meltdown:             Not affected
Vulnerability Mmio stale data:      Not affected
Vulnerability Retbleed:             Not affected
Vulnerability Spec store bypass:    Vulnerable
Vulnerability Spectre v1:           Mitigation; usercopy/swapgs barriers and __user pointer sanitization
Vulnerability Spectre v2:           Mitigation; Retpolines, STIBP disabled, RSB filling, PBRSB-eIBRS Not affe
                                    cted
Vulnerability Srbds:                Not affected
Vulnerability Tsx async abort:      Not affected
Flags:                              fpu vme de pse tsc msr pae mce cx8 apic sep mtrr pge mca cmov pat pse36 c
                                    lflush mmx fxsr sse sse2 ht syscall nx mmxext fxsr_opt pdpe1gb rdtscp lm
                                    constant_tsc rep_good nopl tsc_reliable nonstop_tsc cpuid extd_apicid ape
                                    rfmperf pni pclmulqdq ssse3 fma cx16 pcid sse4_1 sse4_2 movbe popcnt aes
                                    xsave avx f16c rdrand hypervisor lahf_lm cmp_legacy svm cr8_legacy abm ss
                                    e4a misalignsse 3dnowprefetch osvw topoext invpcid_single vmmcall fsgsbas
                                    e bmi1 avx2 smep bmi2 erms invpcid rdseed adx smap clflushopt clwb sha_ni
                                     xsaveopt xsavec xgetbv1 xsaves clzero xsaveerptr rdpru arat npt nrip_sav
                                    e tsc_scale vmcb_clean flushbyasid decodeassists pausefilter pfthreshold
                                    v_vmsave_vmload umip vaes vpclmulqdq rdpid fsrm
```


## [TACO-verified](https://huggingface.co/datasets/likaixin/TACO-verified)

> [!Note]
> We do not use the `leetcode` and `geeksforgeeks` since their poor format.
>
> Actually, this [LeetCode](https://huggingface.co/datasets/newfacade/LeetCodeDataset) dataset is recommended.

### Codeforces

```bash
               Stress Test Summary
╭─────────────────────────┬──────────────────────╮
│ Metric                  │ Value                │
├─────────────────────────┼──────────────────────┤
│ Total Samples           │ 4639                 │
│ Processed Samples       │ 4639                 │
│ Success Rate            │ 98.06%               │
│ Total Time              │ 547.84 seconds       │
│ Throughput              │ 8.47 requests/second │
│ Avg Request Latency     │ 13.97 seconds        │
│ Median Request Latency  │ 13.26 seconds        │
│ Min/Max Request Latency │ 0.04/149.04 seconds  │
│ Avg Execution Time      │ 7.30 seconds         │
│ Median Execution Time   │ 6.27 seconds         │
│ Min/Max Execution Time  │ 0.02/142.03 seconds  │
│ Avg Memory Usage        │ 8.37 MB              │
│ Median Memory Usage     │ 7.00 MB              │
│ Min/Max Memory Usage    │ 0.00/146.00 MB       │
╰─────────────────────────┴──────────────────────╯
            Status Distribution
╭─────────────────────┬───────┬────────────╮
│ Status              │ Count │ Percentage │
├─────────────────────┼───────┼────────────┤
│ accepted            │ 4549  │ 98.06%     │
│ runtime_error       │ 78    │ 1.68%      │
│ system_error        │ 2     │ 0.04%      │
│ time_limit_exceeded │ 1     │ 0.02%      │
│ wrong_answer        │ 9     │ 0.19%      │
╰─────────────────────┴───────┴────────────╯
                                 Performance Percentiles
╭────────────┬───────────────────────────┬──────────────────────────┬───────────────────╮
│ Percentile │ Request Latency (seconds) │ Execution Time (seconds) │ Memory Usage (MB) │
├────────────┼───────────────────────────┼──────────────────────────┼───────────────────┤
│ P50        │ 13.26                     │ 6.27                     │ 7.00              │
│ P75        │ 17.00                     │ 9.74                     │ 8.00              │
│ P90        │ 21.32                     │ 14.00                    │ 8.00              │
│ P95        │ 24.31                     │ 16.90                    │ 10.00             │
│ P99        │ 34.64                     │ 27.11                    │ 38.00             │
╰────────────┴───────────────────────────┴──────────────────────────┴───────────────────╯
```

### aizu

```bash
               Stress Test Summary
╭─────────────────────────┬───────────────────────╮
│ Metric                  │ Value                 │
├─────────────────────────┼───────────────────────┤
│ Total Samples           │ 928                   │
│ Processed Samples       │ 928                   │
│ Success Rate            │ 99.89%                │
│ Total Time              │ 68.85 seconds         │
│ Throughput              │ 13.48 requests/second │
│ Avg Request Latency     │ 8.58 seconds          │
│ Median Request Latency  │ 9.18 seconds          │
│ Min/Max Request Latency │ 0.20/14.38 seconds    │
│ Avg Execution Time      │ 4.54 seconds          │
│ Median Execution Time   │ 4.61 seconds          │
│ Min/Max Execution Time  │ 0.01/8.97 seconds     │
│ Avg Memory Usage        │ 7.87 MB               │
│ Median Memory Usage     │ 8.00 MB               │
│ Min/Max Memory Usage    │ 1.00/52.00 MB         │
╰─────────────────────────┴───────────────────────╯
         Status Distribution
╭──────────────┬───────┬────────────╮
│ Status       │ Count │ Percentage │
├──────────────┼───────┼────────────┤
│ accepted     │ 927   │ 99.89%     │
│ system_error │ 1     │ 0.11%      │
╰──────────────┴───────┴────────────╯
                                 Performance Percentiles
╭────────────┬───────────────────────────┬──────────────────────────┬───────────────────╮
│ Percentile │ Request Latency (seconds) │ Execution Time (seconds) │ Memory Usage (MB) │
├────────────┼───────────────────────────┼──────────────────────────┼───────────────────┤
│ P50        │ 9.18                      │ 4.61                     │ 8.00              │
│ P75        │ 9.70                      │ 4.91                     │ 8.00              │
│ P90        │ 10.30                     │ 5.20                     │ 8.00              │
│ P95        │ 10.66                     │ 5.61                     │ 10.00             │
│ P99        │ 10.99                     │ 6.13                     │ 16.00             │
╰────────────┴───────────────────────────┴──────────────────────────┴───────────────────╯
```

### Codewars

```bash
                Stress Test Summary
╭─────────────────────────┬────────────────────────╮
│ Metric                  │ Value                  │
├─────────────────────────┼────────────────────────┤
│ Total Samples           │ 2072                   │
│ Processed Samples       │ 2072                   │
│ Success Rate            │ 98.75%                 │
│ Total Time              │ 5.75 seconds           │
│ Throughput              │ 360.12 requests/second │
│ Avg Request Latency     │ 0.27 seconds           │
│ Median Request Latency  │ 0.29 seconds           │
│ Min/Max Request Latency │ 0.02/1.70 seconds      │
│ Avg Execution Time      │ 0.03 seconds           │
│ Median Execution Time   │ 0.02 seconds           │
│ Min/Max Execution Time  │ 0.01/1.56 seconds      │
│ Avg Memory Usage        │ 6.85 MB                │
│ Median Memory Usage     │ 7.00 MB                │
│ Min/Max Memory Usage    │ 0.00/181.00 MB         │
╰─────────────────────────┴────────────────────────╯
         Status Distribution
╭───────────────┬───────┬────────────╮
│ Status        │ Count │ Percentage │
├───────────────┼───────┼────────────┤
│ accepted      │ 2046  │ 98.75%     │
│ runtime_error │ 5     │ 0.24%      │
│ wrong_answer  │ 21    │ 1.01%      │
╰───────────────┴───────┴────────────╯
                                 Performance Percentiles
╭────────────┬───────────────────────────┬──────────────────────────┬───────────────────╮
│ Percentile │ Request Latency (seconds) │ Execution Time (seconds) │ Memory Usage (MB) │
├────────────┼───────────────────────────┼──────────────────────────┼───────────────────┤
│ P50        │ 0.29                      │ 0.02                     │ 7.00              │
│ P75        │ 0.36                      │ 0.03                     │ 8.00              │
│ P90        │ 0.37                      │ 0.03                     │ 8.00              │
│ P95        │ 0.39                      │ 0.04                     │ 9.00              │
│ P99        │ 0.54                      │ 0.21                     │ 23.00             │
╰────────────┴───────────────────────────┴──────────────────────────┴───────────────────╯
```

### Codechef

```bash
                Stress Test Summary
╭─────────────────────────┬────────────────────────╮
│ Metric                  │ Value                  │
├─────────────────────────┼────────────────────────┤
│ Total Samples           │ 2667                   │
│ Processed Samples       │ 2667                   │
│ Success Rate            │ 99.48%                 │
│ Total Time              │ 21.73 seconds          │
│ Throughput              │ 122.76 requests/second │
│ Avg Request Latency     │ 0.86 seconds           │
│ Median Request Latency  │ 0.56 seconds           │
│ Min/Max Request Latency │ 0.02/4.97 seconds      │
│ Avg Execution Time      │ 0.41 seconds           │
│ Median Execution Time   │ 0.05 seconds           │
│ Min/Max Execution Time  │ 0.01/4.49 seconds      │
│ Avg Memory Usage        │ 7.97 MB                │
│ Median Memory Usage     │ 7.00 MB                │
│ Min/Max Memory Usage    │ 0.00/121.00 MB         │
╰─────────────────────────┴────────────────────────╯
         Status Distribution
╭───────────────┬───────┬────────────╮
│ Status        │ Count │ Percentage │
├───────────────┼───────┼────────────┤
│ accepted      │ 2653  │ 99.48%     │
│ runtime_error │ 9     │ 0.34%      │
│ system_error  │ 1     │ 0.04%      │
│ wrong_answer  │ 4     │ 0.15%      │
╰───────────────┴───────┴────────────╯
                                 Performance Percentiles
╭────────────┬───────────────────────────┬──────────────────────────┬───────────────────╮
│ Percentile │ Request Latency (seconds) │ Execution Time (seconds) │ Memory Usage (MB) │
├────────────┼───────────────────────────┼──────────────────────────┼───────────────────┤
│ P50        │ 0.56                      │ 0.05                     │ 7.00              │
│ P75        │ 0.71                      │ 0.08                     │ 7.00              │
│ P90        │ 2.03                      │ 1.70                     │ 8.00              │
│ P95        │ 4.12                      │ 3.69                     │ 8.00              │
│ P99        │ 4.66                      │ 4.06                     │ 42.00             │
╰────────────┴───────────────────────────┴──────────────────────────┴───────────────────╯
```

### Atcoder

```bash
                Stress Test Summary
╭─────────────────────────┬───────────────────────╮
│ Metric                  │ Value                 │
├─────────────────────────┼───────────────────────┤
│ Total Samples           │ 1072                  │
│ Processed Samples       │ 1072                  │
│ Success Rate            │ 99.25%                │
│ Total Time              │ 104.78 seconds        │
│ Throughput              │ 10.23 requests/second │
│ Avg Request Latency     │ 11.12 seconds         │
│ Median Request Latency  │ 11.71 seconds         │
│ Min/Max Request Latency │ 0.07/25.19 seconds    │
│ Avg Execution Time      │ 5.85 seconds          │
│ Median Execution Time   │ 5.98 seconds          │
│ Min/Max Execution Time  │ 0.03/16.27 seconds    │
│ Avg Memory Usage        │ 10.30 MB              │
│ Median Memory Usage     │ 7.00 MB               │
│ Min/Max Memory Usage    │ 7.00/162.00 MB        │
╰─────────────────────────┴───────────────────────╯
         Status Distribution
╭───────────────┬───────┬────────────╮
│ Status        │ Count │ Percentage │
├───────────────┼───────┼────────────┤
│ accepted      │ 1064  │ 99.25%     │
│ runtime_error │ 3     │ 0.28%      │
│ system_error  │ 1     │ 0.09%      │
│ wrong_answer  │ 4     │ 0.37%      │
╰───────────────┴───────┴────────────╯
                                 Performance Percentiles
╭────────────┬───────────────────────────┬──────────────────────────┬───────────────────╮
│ Percentile │ Request Latency (seconds) │ Execution Time (seconds) │ Memory Usage (MB) │
├────────────┼───────────────────────────┼──────────────────────────┼───────────────────┤
│ P50        │ 11.71                     │ 5.98                     │ 7.00              │
│ P75        │ 13.17                     │ 6.95                     │ 8.00              │
│ P90        │ 14.67                     │ 8.42                     │ 15.00             │
│ P95        │ 16.13                     │ 9.63                     │ 25.00             │
│ P99        │ 19.39                     │ 11.70                    │ 79.00             │
╰────────────┴───────────────────────────┴──────────────────────────┴───────────────────╯
```

### HackerRank

```bash
                Stress Test Summary
╭─────────────────────────┬────────────────────────╮
│ Metric                  │ Value                  │
├─────────────────────────┼────────────────────────┤
│ Total Samples           │ 699                    │
│ Processed Samples       │ 699                    │
│ Success Rate            │ 99.43%                 │
│ Total Time              │ 3.64 seconds           │
│ Throughput              │ 191.91 requests/second │
│ Avg Request Latency     │ 0.32 seconds           │
│ Median Request Latency  │ 0.33 seconds           │
│ Min/Max Request Latency │ 0.02/2.23 seconds      │
│ Avg Execution Time      │ 0.05 seconds           │
│ Median Execution Time   │ 0.02 seconds           │
│ Min/Max Execution Time  │ 0.00/1.96 seconds      │
│ Avg Memory Usage        │ 9.15 MB                │
│ Median Memory Usage     │ 7.00 MB                │
│ Min/Max Memory Usage    │ 0.00/250.00 MB         │
╰─────────────────────────┴────────────────────────╯
         Status Distribution
╭──────────────┬───────┬────────────╮
│ Status       │ Count │ Percentage │
├──────────────┼───────┼────────────┤
│ accepted     │ 695   │ 99.43%     │
│ system_error │ 2     │ 0.29%      │
│ wrong_answer │ 2     │ 0.29%      │
╰──────────────┴───────┴────────────╯
                                 Performance Percentiles
╭────────────┬───────────────────────────┬──────────────────────────┬───────────────────╮
│ Percentile │ Request Latency (seconds) │ Execution Time (seconds) │ Memory Usage (MB) │
├────────────┼───────────────────────────┼──────────────────────────┼───────────────────┤
│ P50        │ 0.33                      │ 0.02                     │ 7.00              │
│ P75        │ 0.38                      │ 0.03                     │ 8.00              │
│ P90        │ 0.46                      │ 0.04                     │ 8.00              │
│ P95        │ 0.47                      │ 0.10                     │ 18.00             │
│ P99        │ 1.29                      │ 1.11                     │ 85.00             │
╰────────────┴───────────────────────────┴──────────────────────────┴───────────────────╯
```

### HackerEarth

```bash
                Stress Test Summary
╭─────────────────────────┬───────────────────────╮
│ Metric                  │ Value                 │
├─────────────────────────┼───────────────────────┤
│ Total Samples           │ 183                   │
│ Processed Samples       │ 183                   │
│ Success Rate            │ 98.91%                │
│ Total Time              │ 2.76 seconds          │
│ Throughput              │ 66.38 requests/second │
│ Avg Request Latency     │ 0.49 seconds          │
│ Median Request Latency  │ 0.51 seconds          │
│ Min/Max Request Latency │ 0.10/2.27 seconds     │
│ Avg Execution Time      │ 0.11 seconds          │
│ Median Execution Time   │ 0.03 seconds          │
│ Min/Max Execution Time  │ 0.01/1.92 seconds     │
│ Avg Memory Usage        │ 10.61 MB              │
│ Median Memory Usage     │ 7.00 MB               │
│ Min/Max Memory Usage    │ 0.00/575.00 MB        │
╰─────────────────────────┴───────────────────────╯
         Status Distribution
╭──────────────┬───────┬────────────╮
│ Status       │ Count │ Percentage │
├──────────────┼───────┼────────────┤
│ accepted     │ 181   │ 98.91%     │
│ wrong_answer │ 2     │ 1.09%      │
╰──────────────┴───────┴────────────╯
                                 Performance Percentiles
╭────────────┬───────────────────────────┬──────────────────────────┬───────────────────╮
│ Percentile │ Request Latency (seconds) │ Execution Time (seconds) │ Memory Usage (MB) │
├────────────┼───────────────────────────┼──────────────────────────┼───────────────────┤
│ P50        │ 0.51                      │ 0.03                     │ 7.00              │
│ P75        │ 0.54                      │ 0.06                     │ 7.00              │
│ P90        │ 0.61                      │ 0.25                     │ 9.00              │
│ P95        │ 0.96                      │ 0.56                     │ 12.00             │
│ P99        │ 2.11                      │ 1.83                     │ 51.00             │
╰────────────┴───────────────────────────┴──────────────────────────┴───────────────────╯
```

## [LeetCode](https://huggingface.co/datasets/newfacade/LeetCodeDataset)

```bash
                Stress Test Summary
╭─────────────────────────┬────────────────────────╮
│ Metric                  │ Value                  │
├─────────────────────────┼────────────────────────┤
│ Total Samples           │ 2386                   │
│ Processed Samples       │ 2386                   │
│ Success Rate            │ 99.79%                 │
│ Total Time              │ 13.14 seconds          │
│ Throughput              │ 181.56 requests/second │
│ Avg Request Latency     │ 0.33 seconds           │
│ Median Request Latency  │ 0.34 seconds           │
│ Min/Max Request Latency │ 0.03/12.51 seconds     │
│ Avg Execution Time      │ 0.05 seconds           │
│ Median Execution Time   │ 0.04 seconds           │
│ Min/Max Execution Time  │ 0.02/6.60 seconds      │
│ Avg Memory Usage        │ 11.54 MB               │
│ Median Memory Usage     │ 10.00 MB               │
│ Min/Max Memory Usage    │ 8.00/1898.00 MB        │
╰─────────────────────────┴────────────────────────╯
         Status Distribution
╭───────────────┬───────┬────────────╮
│ Status        │ Count │ Percentage │
├───────────────┼───────┼────────────┤
│ accepted      │ 2381  │ 99.79%     │
│ runtime_error │ 1     │ 0.04%      │
│ wrong_answer  │ 4     │ 0.17%      │
╰───────────────┴───────┴────────────╯
                                 Performance Percentiles
╭────────────┬───────────────────────────┬──────────────────────────┬───────────────────╮
│ Percentile │ Request Latency (seconds) │ Execution Time (seconds) │ Memory Usage (MB) │
├────────────┼───────────────────────────┼──────────────────────────┼───────────────────┤
│ P50        │ 0.34                      │ 0.04                     │ 10.00             │
│ P75        │ 0.39                      │ 0.04                     │ 10.00             │
│ P90        │ 0.44                      │ 0.05                     │ 10.00             │
│ P95        │ 0.45                      │ 0.05                     │ 11.00             │
│ P99        │ 0.65                      │ 0.17                     │ 16.00             │
╰────────────┴───────────────────────────┴──────────────────────────┴───────────────────╯
```
