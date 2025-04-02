import requests

row = {
    "id": 0,
    "labels": {
        "execution_language": "python",
        "programming_language": "python",
    },
    "test": [
        {"input": {"stdin": "1"}, "output": {"stdout": "1"}},
        {"input": {"stdin": "2"}, "output": {"stdout": "2"}},
        {"input": {"stdin": "3"}, "output": {"stdout": "3"}},
    ],
}
config = {
    "language": "python",
    "locale": "en",
    "compile_timeout": 20,
    "run_timeout": 20,
    "dataset_type": "CommonOJDataset",
}
config["provided_data"] = row
completion = """
```python
a = int(input())
print(a)
```
"""
response = requests.post(
    "http://localhost:9000/submit",
    json={
        "dataset": "test",
        "id": 0,
        "config": config,
        "completion": completion,
    },
)
completion = """
```python
a = int(input())
print(a)
```
"""
print(response.text)
# assert response.status_code == 200

"""
{
    "id": 0,
    "accepted": true,
    "extracted_code": "a = int(input())\nprint(a)",
    "full_code": null,
    "test_code": null,
    "tests": [
        {
            "passed": true,
            "exec_info": {
                "status": "Success",
                "message": "",
                "compile_result": null,
                "run_result": {
                    "status": "Finished",
                    "execution_time": 0.003359556198120117,
                    "return_code": 0,
                    "stdout": "1\n",
                    "stderr": ""
                },
                "executor_pod_name": null,
                "files": {}
            },
            "test_info": {
                "input": {
                    "stdin": "1"
                },
                "output": {
                    "stdout": "1"
                }
            }
        },
        {
            "passed": true,
            "exec_info": {
                "status": "Success",
                "message": "",
                "compile_result": null,
                "run_result": {
                    "status": "Finished",
                    "execution_time": 0.00995635986328125,
                    "return_code": 0,
                    "stdout": "2\n",
                    "stderr": ""
                },
                "executor_pod_name": null,
                "files": {}
            },
            "test_info": {
                "input": {
                    "stdin": "2"
                },
                "output": {
                    "stdout": "2"
                }
            }
        },
        {
            "passed": true,
            "exec_info": {
                "status": "Success",
                "message": "",
                "compile_result": null,
                "run_result": {
                    "status": "Finished",
                    "execution_time": 0.016722440719604492,
                    "return_code": 0,
                    "stdout": "3\n",
                    "stderr": ""
                },
                "executor_pod_name": null,
                "files": {}
            },
            "test_info": {
                "input": {
                    "stdin": "3"
                },
                "output": {
                    "stdout": "3"
                }
            }
        }
    ],
    "extracted_type": null,
    "extra": null
}
"""
