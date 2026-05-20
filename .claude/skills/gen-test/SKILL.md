---
name: gen-test
description: 为 src/ 下指定模块生成 pytest 测试骨架，遵循项目测试风格
disable-model-invocation: true
---

# 生成 pytest 测试

为指定的源码模块生成测试文件，放到 `tests/` 目录下。

## 要求

1. 先阅读对应的源码文件，理解类/函数签名
2. 按以下结构生成测试：

```python
"""
{模块名} 模块单元测试
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pytest
from src.{package}.{module} import {classes_and_functions}


class Test{ClassName}:
    """{类名}测试"""

    def test_{method_name}(self):
        ...


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
```

3. 每个公开方法至少一个正常路径测试 + 一个异常/边界测试
4. 用类组织同一模块的测试，类名 `Test{ModuleOrClass}`
5. fixture 放在相关的 test class 里
6. 断言用中文消息（如 `"应返回3个条目"`）
7. 生成后运行一次确认全部通过
