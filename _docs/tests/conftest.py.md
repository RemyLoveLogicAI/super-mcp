<details>
<summary>Documentation Metadata (click to expand)</summary>

```json
{
  "doc_type": "file_overview",
  "file_path": "tests/conftest.py",
  "source_hash": "0a8414513e75de67474a495968336058411f8033fa1fa81bd11cd32fe31ec143",
  "last_updated": "2026-02-13T16:48:35.370242+00:00",
  "tokens_used": 64494,
  "complexity_score": 2,
  "estimated_review_time_minutes": 10,
  "external_dependencies": [
    "pytest"
  ]
}
```

</details>

[Documentation Home](../README.md) > [tests](./README.md) > **conftest**

---

# conftest.py

> **File:** `tests/conftest.py`

![Complexity: Low](https://img.shields.io/badge/Complexity-Low-green) ![Review Time: 10min](https://img.shields.io/badge/Review_Time-10min-blue)

## 📑 Table of Contents


- [Overview](#overview)
- [Dependencies](#dependencies)
- [Architecture Notes](#architecture-notes)
- [Usage Examples](#usage-examples)
- [Maintenance Notes](#maintenance-notes)
- [Functions and Classes](#functions-and-classes)

---

## Overview

This module centralizes reusable pytest fixtures for the Super-MCP project so tests can compose deterministic, isolated test state. It supplies filesystem fixtures (a session-scoped tmp directory, a pre-populated skills directory, per-test export/artifact dirs), a session-scoped asyncio event loop, and lightweight instances of domain types (SkillDefinition, ToolDefinition, Event, Checkpoint, Artifact, Session). These fixtures let unit and integration tests get concrete, ready-to-use objects without duplicating construction logic.

Higher-level fixtures provide fresh runtime components created for each test: an EventBus with a bounded buffer, per-test SkillRegistry and ToolRegistry instances, and a SafetyLayer. An async kernel fixture boots a Kernel instance before yielding and ensures shutdown after the test, enabling integration-style tests that require a running kernel. Factory helpers (make_skills, make_tools, make_events) deterministically generate and register multiple items in registries, returning the created lists for assertions.

Design choices emphasize explicit composition and test isolation: Path objects are returned for filesystem fixtures, tempfile.TemporaryDirectory ensures teardown, AsyncMock is used for awaitable callback mocks, and registries are created per-test to avoid cross-test state. The module keeps fixtures small and composable so tests can override or parametrize pieces independently.

## Dependencies

### External Dependencies

| Module | Usage |
| --- | --- |
| `pytest` | import pytest — supplies the @pytest.fixture decorator and fixture machinery used throughout the file. |

### Internal Dependencies

| Module | Usage |
| --- | --- |
| `__future__` | from __future__ import annotations — enables postponed evaluation of annotations so type hints work without runtime imports. |
| `asyncio` | import asyncio — used to create a fresh event loop for session-scoped async tests via asyncio.new_event_loop(). |
| `tempfile` | import tempfile — used to create temporary directories (TemporaryDirectory) for filesystem isolation in tests. |
| `pathlib` | from pathlib import Path — Path objects are returned by filesystem fixtures and used to create/write sample files. |
| `typing` | from typing import AsyncGenerator, Generator — used only in function annotations for fixture signatures. |
| [unittest.mock](../unittest/mock.md) | from unittest.mock import AsyncMock — provides awaitable mock callbacks suitable for EventBus subscriptions in tests. |
| [src.kernel.types](../src/kernel/types.md) | from src.kernel.types import (Artifact, Checkpoint, EntityID, Event, EventTopic, Session, SessionState, SkillDefinition, ToolDefinition, ToolHealth) — used to construct sample domain objects consumed by tests. (EntityID is imported but not referenced in this file.) |
| [src.kernel.event_bus](../src/kernel/event_bus.md) | from src.kernel.event_bus import EventBus — EventBus(buffer_size=1000) is instantiated to provide an isolated event bus for tests. |
| [src.kernel.registry](../src/kernel/registry.md) | from src.kernel.registry import SkillRegistry, ToolRegistry — registries are created per-test; factory fixtures call register(...) to populate them. |
| [src.kernel.safety](../src/kernel/safety.md) | from src.kernel.safety import SafetyLayer — SafetyLayer() is returned by a fixture for tests that need safety checks. |
| [src.kernel.kernel](../src/kernel/kernel.md) | from src.kernel.kernel import Kernel — the async kernel fixture boots a Kernel instance (await k.boot()) before yielding and ensures await k.shutdown() after tests complete. |
| [src.games.engine.state](../src/games/engine/state.md) | from src.games.engine.state import GameState — GameState(max_undo=50) is instantiated by the game_state fixture for game-related tests. |
| [src.games.engine.runner](../src/games/engine/runner.md) | from src.games.engine.runner import GameRunner — GameRunner() is returned by a fixture to provide a runner for game tests. |

## 📁 Directory

This file is part of the **tests** directory. View the [directory index](_docs/tests/README.md) to see all files in this module.

## Architecture Notes

- Small, composable pytest fixtures form the foundation; higher-level fixtures build on these to provide ready-to-use test state.
- Async resources follow pytest async patterns: a session-scoped event loop and an async kernel fixture that boots/shuts down the Kernel to avoid leaked resources.
- Filesystem isolation uses tempfile.TemporaryDirectory and pathlib.Path objects so tests can manipulate files without touching the repo.
- Registries and EventBus are provided per-test to prevent cross-test interference; factory fixtures intentionally call register(...) to create predictable side effects for tests.

## Usage Examples

### Boot a Kernel and perform integration-style operations

A test receives the async 'kernel' fixture which awaits Kernel().boot() before the test runs and ensures Kernel().shutdown() afterwards. Tests can interact with the running kernel to register components or publish events, relying on the fixture to manage lifecycle.

### Create and register multiple generated skills for registry-dependent tests

The make_skills factory fixture constructs N SkillDefinition objects, registers each via skill_registry.register(...), and returns the created list so tests can assert registry state or exercise modules that read from the registry.

### Use a temporary skills directory populated with markdown files

The skills_dir fixture writes sample markdown skill files (e.g., code-review.md, security-audit.md) into a tmp_dir/skills directory. Tests can point loaders at this directory to verify parsing and registration without relying on repository files.

## Maintenance Notes

- The session-scoped event_loop can cause cross-test interactions if tests mutate loop state; consider narrowing scope if isolation issues appear.
- EntityID is imported from src.kernel.types but not used; remove the unused import to avoid linter warnings.
- Kernel.boot()/shutdown() timings affect tests that use the kernel fixture; consider providing a lightweight mock kernel for fast unit tests if needed.
- Factory fixtures mutate registries; if registries gain global state, tests may become flaky—keep registries instance-scoped where possible.

---

## Navigation

**↑ Parent Directory:** [Go up](_docs/tests/README.md)

---

*This documentation was automatically generated by AI ([Woden DocBot](https://github.com/marketplace/ai-document-creator)) and may contain errors. It is the responsibility of the user to validate the accuracy and completeness of this documentation.*


---

## Functions and Classes


#### event_loop

![Type: Sync](https://img.shields.io/badge/Type-Sync-green) ![Generator: Yes](https://img.shields.io/badge/Generator-Yes-purple)

### Signature

```python
def event_loop()
```

### Description

Create a new asyncio event loop, yield it to the caller, and then close it after use.


This function constructs a new asyncio event loop by calling asyncio.new_event_loop(), yields that loop to the caller (it's implemented as a generator), and once the generator is resumed after the yield it closes the loop by calling loop.close(). The implementation contains no parameters and performs no other logic.

### Returns

**Type:** `Generator that yields an asyncio event loop (the function itself yields, does not return)`

When the generator is iterated (or used as a fixture), it yields an asyncio event loop instance created by asyncio.new_event_loop(). After the consumer resumes the generator to finish it, the function closes the loop and the generator completes.


**Possible Values:**

- An instance of asyncio.AbstractEventLoop (concrete event loop object returned by asyncio.new_event_loop())
- Generator completion (None) after loop.close() is executed

### Side Effects

> ❗ **IMPORTANT**
> This function has side effects that modify state or perform I/O operations.

- Calls asyncio.new_event_loop() which allocates/creates a new event loop object
- Calls loop.close() which closes the created event loop and releases associated resources

### Usage Examples

#### Use as a pytest-style generator fixture in tests/conftest.py

```python
def test_something(event_loop):
    # event_loop is the yielded asyncio loop
    # schedule coroutines or run async tests using this loop
    result = event_loop.run_until_complete(some_coroutine())
    assert result == expected
```

Demonstrates consuming the yielded event loop to run coroutines in tests. (The function itself yields the loop and closes it after test finishes.)

#### Direct iteration of the generator (illustrative; generator intended to be used by a framework)

```python
gen = event_loop()
loop = next(gen)  # obtains the new event loop
# use loop
try:
    loop.run_until_complete(coro())
finally:
    try:
        next(gen)  # resume generator so it executes loop.close()
    except StopIteration:
        pass
```

Shows how the generator yields the loop and requires resuming to execute the final close call.

### Complexity

Time complexity: O(1) (creates and closes a single event loop). Space complexity: O(1) (allocates a single event loop object).

### Related Functions

- `asyncio.new_event_loop` - Called by this function to create the event loop
- `loop.close` - Called by this function to close the event loop after yielding

### Notes

- The function is implemented as a generator that yields once and then performs cleanup after the yield resumes.
- No decorator is present in the shown code; in a pytest conftest.py this pattern is commonly used as a fixture (e.g., @pytest.fixture(scope='session') above it), but such a decorator is not present in the provided implementation and is not assumed.
- No explicit exception handling is implemented; any exceptions raised by asyncio.new_event_loop() or loop.close() will propagate to the caller.

---



#### tmp_dir

![Type: Sync](https://img.shields.io/badge/Type-Sync-green) ![Generator: Yes](https://img.shields.io/badge/Generator-Yes-purple)

### Signature

```python
def tmp_dir() -> Generator[Path, None, None]
```

### Description

Provide a temporary filesystem directory path to callers by yielding a pathlib.Path while ensuring the underlying temporary directory is created and (when the context exits) automatically cleaned up.


This function creates a temporary directory using tempfile.TemporaryDirectory with a prefix of 'smcp_test_' and yields a pathlib.Path object pointing to that directory. The TemporaryDirectory context manager ensures the directory is created before yielding and will be removed when the context manager exits. The function itself is a generator that yields exactly one Path value and relies on the with-statement to perform cleanup once the generator's consumer causes the context to exit (in typical usage as a pytest generator fixture, pytest takes care of advancing and finalizing the generator).

### Returns

**Type:** `Generator[Path, None, None]`

A generator that yields a single pathlib.Path representing the path of the created temporary directory.


**Possible Values:**

- A pathlib.Path object pointing to an existing temporary directory created by tempfile.TemporaryDirectory while the context is active

### Side Effects

> ❗ **IMPORTANT**
> This function has side effects that modify state or perform I/O operations.

- Creates a temporary directory on the filesystem using tempfile.TemporaryDirectory
- Removes (deletes) that temporary directory when the TemporaryDirectory context manager exits

### Usage Examples

#### Use as a pytest generator fixture to provide a temporary directory for tests

```python
def test_something(tmp_dir):
    # tmp_dir is a pathlib.Path pointing to a temporary directory
    (tmp_dir / 'file.txt').write_text('data')
    assert (tmp_dir / 'file.txt').exists()
```

Demonstrates typical use in tests where the fixture yields a Path; the temporary directory is available during the test and is cleaned up afterwards.

### Complexity

O(1) time and O(1) auxiliary space: creating the directory is an OS operation with constant-time overhead relative to this function's code; memory usage is constant for the Path object and generator frame.

### Related Functions

- `tempfile.TemporaryDirectory` - Called by this function; provides the underlying temporary directory lifecycle management.
- `pathlib.Path` - Used to convert the temporary directory path string returned by TemporaryDirectory into a Path object returned to callers.

### Notes

- This function is implemented as a generator that yields once; frameworks like pytest that treat generator functions in conftest.py as fixtures will advance and finalize the generator so the TemporaryDirectory cleanup runs after the test.
- If used directly outside a fixture framework, callers must ensure the generator is properly finalized to trigger cleanup (e.g., use it as a fixture or manually close the generator).
- No explicit exception handling is present; underlying calls (tempfile.TemporaryDirectory, filesystem operations) may raise exceptions from the standard library if directory creation fails.

---



#### skills_dir

![Type: Sync](https://img.shields.io/badge/Type-Sync-green)

### Signature

```python
def skills_dir(tmp_dir: Path) -> Path
```

### Description

Create a 'skills' subdirectory inside the provided Path and populate it with three sample Markdown skill files, then return the directory Path.


Given a pathlib.Path representing a temporary directory, the function constructs a subdirectory named 'skills', creates that directory on the filesystem, and writes three Markdown files into it: 'code-review.md', 'security-audit.md', and 'data-analysis.md'. Each file contains a YAML front matter block with name, version, and tags, followed by a Markdown header derived from the filename and a short 'Test skill.' body. Finally, the function returns the Path to the created 'skills' directory.

### Parameters

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `tmp_dir` | `Path` | ✅ | A pathlib.Path pointing to a directory in which a 'skills' subdirectory will be created and populated.
<br>**Constraints:** Must be a writable directory Path, Should exist prior to calling (function does not create parent tmp_dir), If a 'skills' directory already exists, sd.mkdir() will raise FileExistsError |

### Returns

**Type:** `Path`

A pathlib.Path pointing to the newly created 'skills' subdirectory containing the three sample Markdown files.


**Possible Values:**

- Path object for the created 'skills' directory (e.g., tmp_dir / 'skills')

### Raises

| Exception | Condition |
| --- | --- |
| `FileExistsError` | Raised by sd.mkdir() if a directory or file named 'skills' already exists at tmp_dir and mkdir is called without exist_ok=True. |
| `OSError` | Raised for general filesystem-related errors (permission denied, disk full, invalid path) during directory creation or file writes (sd.mkdir() or Path.write_text()). |

### Side Effects

> ❗ **IMPORTANT**
> This function has side effects that modify state or perform I/O operations.

- Creates a directory named 'skills' inside the provided tmp_dir (filesystem mkdir).
- Writes three Markdown files to disk inside that directory: 'code-review.md', 'security-audit.md', 'data-analysis.md'.

### Usage Examples

#### Populate a pytest temporary directory fixture with sample skill files

```python
skills_directory = skills_dir(tmp_path)
# tmp_path is a pytest.Path or pathlib.Path fixture; skills_directory is tmp_path / 'skills'
```

Demonstrates calling the function with a temporary directory to create the 'skills' subdirectory and sample files for tests.

#### Use in test setup to assert file contents

```python
sd = skills_dir(tmp_dir)
assert (sd / 'code-review.md').exists()
content = (sd / 'code-review.md').read_text()
assert 'name: code-review' in content
```

Shows checking that the function created expected files with expected YAML front matter.

### Complexity

Time: O(n) where n is the number of files written (here constant 3, so effectively O(1)). Each write_text call writes the file contents to disk. Space: O(n * s) on disk where s is average size of each file; in-memory usage is O(1) aside from the temporary strings created for writing.

### Related Functions

- `tmp_path / tmpdir fixtures (pytest)` - Commonly used together; tmp_dir is expected to be a Path-like temporary directory provided by test harness (e.g., pytest's tmp_path).

### Notes

- Uses pathlib.Path operations: path division (/) to build file paths and write_text to write files.
- sd.mkdir() is called without exist_ok=True, so the function will raise if the 'skills' directory already exists.
- The file contents include a YAML front matter block and a Markdown header; names are derived directly from the filename strings and transformed for the header using replace and title.
- No input validation is performed on tmp_dir beyond relying on Path methods; callers should ensure tmp_dir is a valid, writable directory Path.

---



#### exports_dir

![Type: Sync](https://img.shields.io/badge/Type-Sync-green)

### Signature

```python
def exports_dir(tmp_dir: Path) -> Path
```

### Description

Create a subdirectory named 'exports' inside the provided Path and return its Path object.


Given a Path object tmp_dir, the function constructs a child path by combining tmp_dir with the string 'exports' (using the Path '/' operator), creates that directory on the filesystem using Path.mkdir(), and returns the Path object referencing the newly created directory. There is no special handling for existing directories; errors from Path.mkdir() propagate.

### Parameters

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `tmp_dir` | `Path` | ✅ | Base directory in which an 'exports' subdirectory will be created.
<br>**Constraints:** Should be a pathlib.Path (or compatible object) representing a directory path, Parent filesystem location must allow directory creation (permissions, existence) |

### Returns

**Type:** `Path`

A pathlib.Path object pointing to the created 'exports' subdirectory (tmp_dir / 'exports').


**Possible Values:**

- A Path instance for the newly created directory when creation succeeds
- No return if an exception is raised before returning

### Raises

| Exception | Condition |
| --- | --- |
| `FileExistsError` | If the path exists as a file (or if mkdir semantics cause this) and the underlying Path.mkdir() raises FileExistsError. |
| `OSError` | For other filesystem-related errors from Path.mkdir(), e.g., permission denied, invalid path, disk errors. |

### Side Effects

> ❗ **IMPORTANT**
> This function has side effects that modify state or perform I/O operations.

- Creates a directory on the filesystem (calls Path.mkdir())

### Usage Examples

#### Create an 'exports' directory inside a temporary directory

```python
exports_path = exports_dir(tmp_dir)
```

Creates tmp_dir/exports on disk and returns the Path object for that directory.

### Complexity

Time complexity: O(1) (single path construction and a single filesystem mkdir call). Space complexity: O(1) additional memory (one Path object).

### Related Functions

- `Path.mkdir` - Called by this function to create the directory on the filesystem

### Notes

- The function does not pass exist_ok=True to mkdir(), so if the directory already exists or mkdir encounters a conflict, an exception from Path.mkdir() will be raised.
- The function relies on pathlib.Path semantics for the '/' operator to build the child path.
- No input validation is performed beyond relying on Path methods; callers should ensure tmp_dir is an appropriate Path.

---



#### sample_skill

![Type: Sync](https://img.shields.io/badge/Type-Sync-green)

### Signature

```python
def sample_skill() -> SkillDefinition
```

### Description

Returns a minimal SkillDefinition instance pre-filled with test data.


This function constructs and returns a SkillDefinition object initialized with fixed test values: name 'test-skill', description 'A skill used in tests', version '1.0.0', tags ['test', 'fixture'], a single parameter entry for 'input' of type 'string' marked required, and one example mapping input 'hello' to output 'world'. The function contains no branching or computation beyond creating and returning this SkillDefinition instance.

### Returns

**Type:** `SkillDefinition`

A SkillDefinition object populated with a minimal set of fields used for testing purposes.


**Possible Values:**

- A SkillDefinition instance with the following literal contents: {name: 'test-skill', description: 'A skill used in tests', version: '1.0.0', tags: ['test','fixture'], parameters: [{'name':'input','type':'string','required': True}], examples: [{'input':'hello','output':'world'}]}
- Any equivalent SkillDefinition object instance created by the constructor with the same field values

### Usage Examples

#### Obtain a simple test SkillDefinition to use in unit tests or fixtures

```python
skill = sample_skill()
```

Demonstrates calling the function to receive the predefined SkillDefinition instance for use in tests.

### Complexity

O(1) time complexity and O(1) space complexity — the function performs a single object construction and returns it.

### Related Functions

- `SkillDefinition` - Constructs and returns an instance of this class/type

### Notes

- The function expects SkillDefinition to be defined or imported in the module scope where sample_skill is used; the function itself does not import or define SkillDefinition.
- No validation is performed on the provided literal values; the behavior depends on the SkillDefinition constructor implementation.
- This function is a deterministic factory that always returns the same data values.

---



#### sample_tool

![Type: Sync](https://img.shields.io/badge/Type-Sync-green)

### Signature

```python
def sample_tool() -> ToolDefinition
```

### Description

Returns a pre-configured ToolDefinition instance used for testing.


This function constructs and returns a ToolDefinition object populated with fixed, hard-coded values intended as a minimal test fixture. The returned object includes name, description, category, authentication settings, a health check URL, an explicit health status, version, and tags. There is no conditional logic or external interaction in this function; it simply instantiates and returns the ToolDefinition with the specified literal values.

### Returns

**Type:** `ToolDefinition`

A ToolDefinition instance created with fixed test-oriented attributes.


**Possible Values:**

- ToolDefinition(name='test-tool', description='A tool used in tests', category='testing', auth_required=False, auth_scopes=[], health_check_url='https://httpbin.org/get', health=ToolHealth.HEALTHY, version='1.0.0', tags=['test', 'fixture'])

### Usage Examples

#### Obtain a test ToolDefinition fixture for unit tests or test setup

```python
tool = sample_tool()
```

Demonstrates creating the pre-configured ToolDefinition instance for use in tests.

### Complexity

O(1) time and O(1) space — constant time and space to instantiate and return a single object.

### Related Functions

- `ToolDefinition` - Constructor called to create and return the object
- `ToolHealth` - Enum/constant referenced to set the health field on the created object

### Notes

- The function uses literal, hard-coded values and does not accept parameters.
- No validation, I/O, or side effects are performed; it is suitable as a simple test fixture.
- If the ToolDefinition constructor signature changes, this function must be updated accordingly.

---



#### sample_event

![Type: Sync](https://img.shields.io/badge/Type-Sync-green)

### Signature

```python
def sample_event() -> Event
```

### Description

Return a minimal Event instance configured for testing.


Constructs and returns a new Event object with fixed fields intended for use in tests. The function calls the Event constructor with source set to the string "test", topic set to EventTopic.SYSTEM, action set to "test.action", and payload set to the dict {"key": "value"}. It does not take any inputs and always returns the same pattern of Event.

### Returns

**Type:** `Event`

An Event instance constructed with the following fixed values: source='test', topic=EventTopic.SYSTEM, action='test.action', payload={'key': 'value'}.


**Possible Values:**

- An Event object with source='test', topic=EventTopic.SYSTEM, action='test.action', payload={'key': 'value'}

### Usage Examples

#### Create a reusable test event to pass into code under test

```python
evt = sample_event()
assert evt.source == 'test'
# pass evt to functions that accept an Event
```

Demonstrates obtaining the standardized Event instance produced by this helper and checking one of its fields before using it in tests.

### Complexity

O(1) time and O(1) space (constant-time construction of a single object).

### Related Functions

- `Event` - Calls the Event constructor to create and return the Event instance.
- `EventTopic.SYSTEM` - References this enum/constant value to set the event topic.

### Notes

- This helper returns a fixed, minimal Event suitable for tests; it does not accept parameters to customize the returned Event.
- If the Event constructor or EventTopic enum changes, this helper should be updated accordingly.

---



#### sample_checkpoint

![Type: Sync](https://img.shields.io/badge/Type-Sync-green)

### Signature

```python
def sample_checkpoint() -> Checkpoint
```

### Description

Returns a newly constructed Checkpoint instance with a fixed name and state for use in tests.


This function constructs and returns a Checkpoint object using a literal name "test-checkpoint" and a literal state dictionary {'counter': 42, 'items': ['a', 'b']}. The function contains no branching or computation beyond creating and returning the Checkpoint instance; it is a small factory/helper used in tests to provide a minimal, deterministic Checkpoint value.

### Returns

**Type:** `Checkpoint`

A Checkpoint instance created with name="test-checkpoint" and state={'counter': 42, 'items': ['a', 'b']}.


**Possible Values:**

- Checkpoint(name='test-checkpoint', state={'counter': 42, 'items': ['a', 'b']})

### Usage Examples

#### Providing a minimal checkpoint object for unit tests or fixtures

```python
cp = sample_checkpoint()
```

Creates a Checkpoint instance with a known name and state to be used in assertions or passed to functions under test.

### Complexity

O(1) time complexity and O(1) space complexity (constant-time construction of a small object).

### Notes

- The function references the Checkpoint type and returns an instance; the definition or import of Checkpoint is not shown in this snippet and must be available in the test module context.
- This is a deterministic helper intended for tests; it always returns the same contents.

---



#### sample_artifact

![Type: Sync](https://img.shields.io/badge/Type-Sync-green)

### Signature

```python
def sample_artifact(tmp_dir: Path) -> Artifact
```

### Description

Return a newly constructed Artifact instance with fixed test values.


This function creates and returns an Artifact object initialized with hard-coded test data: name 'test-artifact', markdown content '# Test Artifact\n\nHello, world.\n', format 'md', and tags ['test']. The supplied parameter tmp_dir is accepted but not used in the implementation.

### Parameters

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `tmp_dir` | `Path` | ✅ | A Path object provided to the function (not used by this implementation).
<br>**Constraints:** No validation or usage in the function body; any Path-like value may be passed but has no effect |

### Returns

**Type:** `Artifact`

An Artifact instance constructed with fixed test properties (name, content, format, tags).


**Possible Values:**

- An Artifact object with: name='test-artifact', content="# Test Artifact\n\nHello, world.\n", format='md', tags=['test']

### Usage Examples

#### Create a minimal Artifact for a unit test when a tmp_dir fixture is available

```python
artifact = sample_artifact(tmp_dir)
```

Demonstrates calling the helper to obtain a ready-to-use Artifact with consistent test data. The tmp_dir argument is accepted but ignored.

### Complexity

O(1) time and O(1) additional space — creates a single Artifact instance with constant-size data.

### Notes

- The tmp_dir parameter is unused in the function body; it likely exists to match test fixture signatures or future expansion.
- The function returns a concrete Artifact constructed directly; no validation or mutation occurs.
- If the Artifact constructor performs validation or side effects, those are not visible in this function's code and are not documented here.

---



#### sample_session

![Type: Sync](https://img.shields.io/badge/Type-Sync-green)

### Signature

```python
def sample_session() -> Session
```

### Description

Returns a newly constructed Session object with its state set to SessionState.RUNNING.


This function constructs and returns a minimal Session instance intended for tests. It calls the Session constructor with a single keyword argument: state set to SessionState.RUNNING. There is no additional logic, branching, or mutation beyond creating and returning that Session object.

### Returns

**Type:** `Session`

A Session instance created by calling Session(state=SessionState.RUNNING).


**Possible Values:**

- A Session object whose 'state' attribute equals SessionState.RUNNING

### Usage Examples

#### Create a test session with running state for use in unit tests

```python
session = sample_session()
```

Demonstrates calling the helper to obtain a Session preconfigured with SessionState.RUNNING.

### Complexity

O(1) time and O(1) space — constructs and returns a single object with a fixed number of arguments.

### Related Functions

- `Session` - Called by sample_session — the constructor invoked to create the returned object.
- `SessionState.RUNNING` - Used as the value passed into Session to set the session's state.

### Notes

- This function assumes Session and SessionState are available in scope (imported or defined elsewhere in the test module).
- No validation or error handling is performed here; any exceptions would come from the Session constructor or related imports.

---



#### event_bus

![Type: Sync](https://img.shields.io/badge/Type-Sync-green)

### Signature

```python
def event_bus() -> EventBus
```

### Description

Return a newly constructed EventBus instance configured with buffer_size=1000.


This function creates and returns a new EventBus by calling the EventBus constructor with a single keyword argument buffer_size set to 1000. The function does not accept any parameters and forwards the fixed configuration to the EventBus constructor before returning the created object.

### Returns

**Type:** `EventBus`

A newly instantiated EventBus object constructed with buffer_size=1000.


**Possible Values:**

- An EventBus instance (constructed via EventBus(buffer_size=1000))

### Usage Examples

#### Obtain a fresh EventBus for tests or local usage

```python
bus = event_bus()
```

Creates an EventBus instance with buffer_size set to 1000 and assigns it to the variable bus.

### Complexity

O(1) time and O(1) space — the function performs a single constructor call and returns its result.

### Related Functions

- `EventBus` - Calls/constructs — this function calls the EventBus constructor to produce the return value.

### Notes

- The function body is a direct, single-line factory wrapper around EventBus(buffer_size=1000).
- No parameters or configuration options are exposed by this function; buffer_size is fixed to 1000 in the call visible in the implementation.

---



#### skill_registry

![Type: Sync](https://img.shields.io/badge/Type-Sync-green)

### Signature

```python
def skill_registry() -> SkillRegistry
```

### Description

Return a newly constructed SkillRegistry instance.

This zero-argument function constructs and returns a new SkillRegistry by calling its constructor and returning the resulting object. The implementation contains only a direct call to SkillRegistry() and returns that instance; there is no additional initialization, configuration, or logic in this wrapper.

### Returns

**Type:** `SkillRegistry`

A fresh instance of the SkillRegistry class created by calling its constructor.


**Possible Values:**

- An instance of SkillRegistry

### Usage Examples

#### Obtain a fresh SkillRegistry for use in tests or fixtures

```python
registry = skill_registry()
```

Demonstrates calling the function to receive a new SkillRegistry instance.

### Complexity

O(1) time and O(1) additional space (aside from the memory allocated by SkillRegistry() for the returned instance).

### Related Functions

- `SkillRegistry` - Constructor called by this function; this function is a thin wrapper that returns a new SkillRegistry instance.

### Notes

- The function takes no parameters and performs no validation.
- Any behavior, side effects, or exceptions depend entirely on SkillRegistry.__init__ implementation, which is not shown here.

---



#### tool_registry

![Type: Sync](https://img.shields.io/badge/Type-Sync-green)

### Signature

```python
def tool_registry() -> ToolRegistry
```

### Description

Returns a newly constructed ToolRegistry instance.

This function calls the ToolRegistry constructor with no arguments and returns the resulting object. The implementation is a single return statement that constructs and returns ToolRegistry(). There is no additional logic, configuration, or state mutation performed inside this function.

### Returns

**Type:** `ToolRegistry`

A new instance of the ToolRegistry class constructed by calling ToolRegistry().


**Possible Values:**

- An instance of ToolRegistry (constructed object)

### Usage Examples

#### Obtain a fresh ToolRegistry instance for tests or fixtures

```python
registry = tool_registry()
```

Demonstrates calling the function to receive a newly constructed ToolRegistry object.

### Complexity

O(1) time complexity and O(1) space complexity (single object construction and return)

### Related Functions

- `ToolRegistry` - Constructor called by this function to produce the return value

### Notes

- The function body is a direct call to ToolRegistry() and returns that object; no parameters are accepted.
- Any behavior, exceptions, or side effects beyond constructing ToolRegistry depend entirely on the ToolRegistry constructor implementation, which is not shown here.

---



#### safety_layer

![Type: Sync](https://img.shields.io/badge/Type-Sync-green)

### Signature

```python
def safety_layer() -> SafetyLayer
```

### Description

Return a new SafetyLayer instance created with its default constructor.


The function calls the SafetyLayer constructor with no arguments and returns the newly created object. There is no additional logic, configuration, or handling; it simply forwards to SafetyLayer() and returns that instance. The docstring states it provides a SafetyLayer with default rules, but the function implementation only constructs and returns SafetyLayer() without modifying it.

### Returns

**Type:** `SafetyLayer`

A newly constructed SafetyLayer object returned from calling SafetyLayer() with no arguments.


**Possible Values:**

- An instance of SafetyLayer constructed by SafetyLayer()

### Usage Examples

#### Obtain a default-configured SafetyLayer instance for use in tests or setup code

```python
safety = safety_layer()
```

Calls the function which constructs and returns a SafetyLayer instance using its default constructor.

### Complexity

Time: O(1) — the function performs a single constructor call and return. Space: O(1) additional — only the new SafetyLayer instance allocation (cost depends on SafetyLayer constructor).

### Related Functions

- `SafetyLayer` - Constructor/class invoked by this function; safety_layer returns an instance of this class.

### Notes

- The function contains no logic beyond calling SafetyLayer() and returning the result.
- Any behavior, configuration, or side effects depend entirely on SafetyLayer.__init__ and are not visible in this function's implementation.

---



#### async 

![Type: Async](https://img.shields.io/badge/Type-Async-blue) ![Generator: Yes](https://img.shields.io/badge/Generator-Yes-purple)

### Signature

```python
async def kernel() -> AsyncGenerator[Kernel, None]
```

### Description

Provides an async test fixture that yields a booted Kernel instance and ensures it is shut down after use.


This function is an asynchronous generator intended for use as a test fixture. It constructs a Kernel instance, awaits its boot() coroutine to perform any startup work, yields the Kernel to the caller, and after the caller resumes the fixture it awaits k.shutdown() to perform cleanup. The generator ensures that shutdown is awaited after the yielded Kernel is used by the test. The implementation shows direct calls to Kernel(), k.boot(), and k.shutdown() and yields the Kernel instance between boot and shutdown steps.

### Returns

**Type:** `AsyncGenerator[Kernel, None]`

An async generator that yields a single Kernel instance (the Kernel object created and booted). The generator does not return a value after completion; instead it performs shutdown as cleanup.


**Possible Values:**

- Yields a Kernel instance once, then completes after awaiting shutdown
- If an exception occurs during boot or while the caller uses the yielded Kernel, the shutdown coroutine may not be reached (the exception will propagate)

### Raises

| Exception | Condition |
| --- | --- |
| `Any exception raised by Kernel.boot or Kernel.shutdown or Kernel constructor` | If Kernel() constructor, k.boot(), or k.shutdown() raise, those exceptions propagate out of this generator; there are no explicit try/except handlers in this function |

### Side Effects

> ❗ **IMPORTANT**
> This function has side effects that modify state or perform I/O operations.

- Constructs a Kernel instance (calls Kernel())
- Performs asynchronous startup by awaiting k.boot()
- Performs asynchronous cleanup by awaiting k.shutdown()

### Usage Examples

#### As a pytest async fixture to provide a booted kernel to a test

```python
async for k in kernel():
    # use k inside test
    ...
```

Demonstrates yielding the booted Kernel instance; after the test finishes using the yielded instance the fixture awaits k.shutdown() as cleanup.

#### Typical pytest-asyncio usage (conceptual)

```python
@pytest.mark.asyncio
async def test_something(kernel):
    # kernel would be provided by the fixture system; this example shows intended usage
    assert kernel is not None
```

Shows how the fixture would be injected into an async test. (Actual fixture registration not shown in this snippet.)

### Complexity

Time: O(1) excluding the cost of Kernel.boot()/Kernel.shutdown(); Space: O(1) additional stack/memory aside from the Kernel instance

### Related Functions

- `Kernel.boot` - Called by this function to start the Kernel
- `Kernel.shutdown` - Called by this function to shut down the Kernel after the yield

### Notes

- This implementation yields the Kernel once and relies on the caller/test harness to resume the generator to trigger the asynchronous shutdown.
- No exception handling is present in the fixture; any exceptions raised by Kernel methods will propagate to the caller.
- This is an async generator function (used as a fixture pattern in async test frameworks); it must be iterated/used in an async context to execute boot and shutdown.

---



#### game_state

![Type: Sync](https://img.shields.io/badge/Type-Sync-green)

### Signature

```python
def game_state() -> GameState
```

### Description

Returns a newly constructed GameState instance configured with max_undo set to 50.


This function creates and returns a fresh GameState object by calling the GameState constructor with the keyword argument max_undo=50. The implementation consists of a single return statement and does not perform any additional logic, validation, or side effects.

### Returns

**Type:** `GameState`

A new GameState instance created by calling GameState(max_undo=50).


**Possible Values:**

- An instance of GameState configured with its max_undo attribute (or constructor parameter) set to 50

### Usage Examples

#### Obtain a test fixture GameState for use in tests

```python
state = game_state()
```

Demonstrates calling the function to get a fresh GameState instance with max_undo=50 for use in test setup.

### Complexity

O(1) time and O(1) additional space: constructs a single object and returns it.

### Related Functions

- `GameState` - Constructs/instantiates the GameState class (this function calls the GameState constructor).

### Notes

- The function body is a single return of GameState(max_undo=50); no other behavior is present in the code shown.
- Any behavior or attributes of the returned object depend entirely on GameState's implementation, which is not shown here.

---



#### game_runner

![Type: Sync](https://img.shields.io/badge/Type-Sync-green)

### Signature

```python
def game_runner() -> GameRunner
```

### Description

Returns a new GameRunner instance created with no games registered.


This function constructs and returns a fresh GameRunner by calling its zero-argument constructor. The implementation contains a single return statement that invokes GameRunner() and returns that object. There is no additional initialization, mutation, or registration performed within this function.

### Returns

**Type:** `GameRunner`

A newly constructed GameRunner object created by calling GameRunner() with no arguments.


**Possible Values:**

- An instance of GameRunner created via GameRunner() (with whatever default internal state GameRunner's constructor provides).

### Usage Examples

#### Obtain a fresh GameRunner instance for use in tests or other code

```python
runner = game_runner()
```

Demonstrates calling the function to receive a new GameRunner object constructed with the default constructor.

### Complexity

O(1) time and O(1) additional space (constructing a single object; actual constructor complexity depends on GameRunner.__init__).

### Related Functions

- `GameRunner.__init__` - Called by this function; the returned object's initial state is determined by GameRunner's constructor.

### Notes

- The function performs no operations beyond calling GameRunner(). Any behavior beyond object construction (such as registering games) is determined entirely by GameRunner's constructor and not by this function.
- Implementation is a single-line wrapper; there are no parameters and no error handling in this function itself.

---



#### mock_event_callback

![Type: Sync](https://img.shields.io/badge/Type-Sync-green)

### Signature

```python
def mock_event_callback() -> AsyncMock
```

### Description

Return a new AsyncMock instance by invoking AsyncMock() (an AsyncMock suitable for event bus subscription).


This function contains a single statement that constructs and returns a new AsyncMock object by calling AsyncMock() with no arguments. There is no additional logic, branching, or side effects. The docstring indicates the returned AsyncMock is intended to be used for event bus subscription, but the implementation only creates and returns the AsyncMock instance.

### Returns

**Type:** `AsyncMock`

A newly created AsyncMock instance (constructed by calling AsyncMock()).


**Possible Values:**

- An AsyncMock instance

### Usage Examples

#### Create a mock async callback to subscribe to an event bus or pass into async code during tests

```python
mock_cb = mock_event_callback()
# use mock_cb as an awaitable/mock callback in tests
```

Demonstrates calling the function to obtain an AsyncMock instance to be used where an async callback is expected.

### Complexity

Time complexity: O(1) — constant time to construct and return an object. Space complexity: O(1) additional space aside from the created AsyncMock instance.

### Related Functions

- `AsyncMock` - Constructed by this function; the function returns an instance of AsyncMock.

### Notes

- The function body is a single constructor call returning AsyncMock().
- The implementation assumes AsyncMock is available in the scope where this function is defined; the function itself does not perform imports.
- The docstring indicates intended use (event bus subscription) but that behavior is not enforced by the function implementation.

---



#### mock_llm_response

![Type: Sync](https://img.shields.io/badge/Type-Sync-green)

### Signature

```python
def mock_llm_response() -> dict
```

### Description

Returns a static, hard-coded dictionary representing a mock LLM response payload for tests.


This function constructs and returns a literal Python dictionary that mimics the structure of a language-model response. The returned dictionary contains top-level keys 'id', 'model', 'choices', and 'usage'. 'choices' is a list with a single choice entry that includes 'index', 'message' (with 'role' and 'content'), and 'finish_reason'. 'usage' contains integer token counts. There is no computation, branching, I/O, or external calls — the function simply returns the predefined dictionary.

### Returns

**Type:** `dict`

A dictionary representing a mock LLM response payload used in tests. Structure exactly as returned by the function.


**Possible Values:**

- {
  "id": "mock-response-001",
  "model": "test-model",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "This is a mock response for testing."
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 10,
    "completion_tokens": 20,
    "total_tokens": 30
  }
}

### Usage Examples

#### Use in unit tests to provide a deterministic LLM-like response payload

```python
response = mock_llm_response()
# assert response['id'] == 'mock-response-001'
# assert response['choices'][0]['message']['content'] == 'This is a mock response for testing.'
```

Demonstrates calling the function and inspecting fields in the returned mock payload for assertions in tests.

### Complexity

O(1) time and O(1) additional space (returns a fixed-size literal); complexity does not depend on input size since there are no inputs.

### Notes

- The function is deterministic and returns the same literal dictionary on every call.
- There are no side effects, so it is safe to call repeatedly in tests.
- If tests require variations, callers must copy and modify the returned dict; the function itself does not accept parameters to customize output.

---



#### make_skills

![Type: Sync](https://img.shields.io/badge/Type-Sync-green)

### Signature

```python
def make_skills(skill_registry: SkillRegistry) -> Callable[[int], list[SkillDefinition]]
```

### Description

Factory fixture that returns a helper function which registers a number of generated SkillDefinition objects in the given SkillRegistry and returns them as a list.


make_skills accepts a SkillRegistry and defines an inner factory function _make(count: int = 5) that: creates 'count' SkillDefinition instances with deterministic names, descriptions, version, tags, empty parameters and examples; registers each created SkillDefinition with the provided skill_registry by calling skill_registry.register(s); collects the created SkillDefinition objects in a list and returns that list. The outer function returns the inner _make factory so callers can generate and register batches of skills on demand (typical use as a pytest fixture factory).

### Parameters

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `skill_registry` | `SkillRegistry` | ✅ | Registry object used to register each generated SkillDefinition via its register method.
<br>**Constraints:** Must provide a .register(skill: SkillDefinition) method, No runtime type checks are performed in this function |

### Returns

**Type:** `Callable[[int], list[SkillDefinition]]`

A factory function _make that accepts an optional integer count (default 5) and returns a list of SkillDefinition objects after registering each with the provided skill_registry.


**Possible Values:**

- List of SkillDefinition instances of length equal to the provided count (count >= 0)
- Empty list if count is 0

### Side Effects

> ❗ **IMPORTANT**
> This function has side effects that modify state or perform I/O operations.

- Calls skill_registry.register(s) for each generated SkillDefinition, mutating the provided registry's state

### Usage Examples

#### Use as a pytest fixture factory to create and register 3 generated skills

```python
factory = make_skills(my_skill_registry)
skills = factory(3)
```

Demonstrates obtaining the returned factory from make_skills and using it to create and register three SkillDefinition instances; 'skills' will contain the three created instances.

#### Default usage (creates 5 skills)

```python
factory = make_skills(my_skill_registry)
skills = factory()
```

Calls the returned factory without arguments to create and register 5 generated skills (default count).

### Complexity

Time: O(n) where n is the count argument (each iteration constructs a SkillDefinition and performs one register call). Space: O(n) additional memory for the returned list of SkillDefinition objects.

### Related Functions

- `SkillRegistry.register` - Called by this function to register each generated SkillDefinition.
- `SkillDefinition` - Constructor is invoked to create each generated skill instance.

### Notes

- The code does not validate the count argument (e.g., negative values). Passing a negative count will result in zero iterations because range(count) with negative count yields no iterations.
- Tags are generated deterministically as ['generated', f'batch-{i % 3}'] and parameters/examples are empty lists.
- No exceptions are explicitly raised by this function; any exception would come from the SkillDefinition constructor or skill_registry.register implementation.

---



#### _make

![Type: Sync](https://img.shields.io/badge/Type-Sync-green)

### Signature

```python
def _make(count: int = 5) -> list[SkillDefinition]
```

### Description

Constructs a list of SkillDefinition instances (default 5), registers each with skill_registry, and returns the list.


This helper function iterates count times, creating a new SkillDefinition on each iteration with deterministic values derived from the loop index (name, description, version, tags, parameters, examples). After creating each SkillDefinition, it calls skill_registry.register(s) to register the skill, appends the instance to a local list, and finally returns the list of created SkillDefinition objects. The function uses formatted strings to set name and description and cycles a tag value using i % 3.

### Parameters

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `count` = `5` | `int` | ❌ | Number of SkillDefinition instances to create and register.
<br>**Constraints:** Expected to be a non-negative integer (function does not explicitly validate), If count is 0, the function returns an empty list |

### Returns

**Type:** `list[SkillDefinition]`

A list containing the SkillDefinition instances that were created and registered.


**Possible Values:**

- A list with length equal to count containing SkillDefinition objects
- An empty list if count is 0

### Side Effects

> ❗ **IMPORTANT**
> This function has side effects that modify state or perform I/O operations.

- Calls skill_registry.register(s) for each created SkillDefinition, which mutates external/global registry state
- Appends created SkillDefinition objects to a local list returned to the caller (local mutation)

### Usage Examples

#### Create and register the default number of generated skills in tests

```python
_make()
```

Generates 5 SkillDefinition instances, registers each with skill_registry, and returns the list.

#### Create and register a specific number of generated skills

```python
_make(10)
```

Generates 10 SkillDefinition instances, registers each with skill_registry, and returns the list of 10 objects.

### Complexity

Time complexity O(count) — performs a constant amount of work per created item. Space complexity O(count) for the returned list (plus whatever skill_registry.register stores internally).

### Related Functions

- `skill_registry.register` - Called by _make to register each created SkillDefinition; external dependency that produces the side effect of registering the skill.

### Notes

- The function does not perform input validation on count; negative values will cause range(count) to behave accordingly (no iterations for non-positive integers).
- Potential exceptions may propagate from SkillDefinition(...) construction or skill_registry.register(...) calls, but the function itself does not catch or raise explicit exceptions.
- The SkillDefinition type and skill_registry are assumed to be available in the module scope; this function relies on those definitions/objects being present.

---



#### make_tools

![Type: Sync](https://img.shields.io/badge/Type-Sync-green)

### Signature

```python
def make_tools(tool_registry: ToolRegistry) -> Callable[[int], list[ToolDefinition]]
```

### Description

Factory fixture that creates and registers a specified number of ToolDefinition instances in the provided tool_registry and returns them as a list.


make_tools is a higher-order function (a factory fixture commonly used in tests) that accepts a tool_registry object and returns an inner function _make. When called, _make(n) constructs n ToolDefinition instances with incremented names and predictable fields (name, description, category, auth flags, health_check_url, health, version, tags). Each created ToolDefinition is registered by calling tool_registry.register(t) and appended to a list which is returned. The default number of tools created by _make is 5.

### Parameters

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `tool_registry` | `ToolRegistry` | ✅ | Registry object into which each generated ToolDefinition will be registered via its register method.
<br>**Constraints:** Must provide a register(tool: ToolDefinition) method (the function calls tool_registry.register(t)). |

### Returns

**Type:** `Callable[[int], list[ToolDefinition]]`

Returns a callable _make that, when invoked with an integer count, creates that many ToolDefinition instances, registers each with the provided tool_registry, and returns a list of the created ToolDefinition objects.


**Possible Values:**

- A function _make(count: int = 5) -> list[ToolDefinition]

### Side Effects

> ❗ **IMPORTANT**
> This function has side effects that modify state or perform I/O operations.

- Calls tool_registry.register(t) for each generated ToolDefinition, mutating the provided tool_registry (registers tools into the registry).
- Instantiates ToolDefinition objects (allocates objects in memory).

### Usage Examples

#### In a test setup to create and register 3 tools

```python
creator = make_tools(my_tool_registry)
tools = creator(3)
```

Demonstrates obtaining the _make callable from make_tools and creating/registering 3 ToolDefinition instances in my_tool_registry; tools is the list of created ToolDefinition objects.

#### Using default count

```python
creator = make_tools(my_tool_registry)
default_tools = creator()
```

Calls _make with the default parameter (5) to create and register five tools.

### Complexity

Time complexity: O(n) where n is the count argument passed to the returned _make function (loop that constructs and registers n ToolDefinition objects). Space complexity: O(n) for the list of returned ToolDefinition instances.

### Related Functions

- `ToolRegistry.register` - Called by make_tools/_make to register each created ToolDefinition.
- `ToolDefinition` - Constructor is invoked to create each tool instance.

### Notes

- make_tools returns an inner function _make; the outer function itself does not create tools until the returned callable is invoked.
- Default number of created tools is 5 when _make is called with no arguments.
- No explicit error handling is present; any exception raised by ToolDefinition construction or tool_registry.register will propagate to the caller.
- This pattern is typical for pytest fixtures defined in tests/conftest.py — make_tools likely used to provide test data by registering tools in a shared registry.

---



#### _make

![Type: Sync](https://img.shields.io/badge/Type-Sync-green)

### Signature

```python
def _make(count: int = 5) -> list[ToolDefinition]
```

### Description

Create a list of ToolDefinition instances and register each one in the shared tool_registry, then return the list.


This function iterates count times (default 5). On each iteration it constructs a ToolDefinition with predictable, generated values (name, description, category, auth settings, health_check_url, health, version, tags). After creating each ToolDefinition instance it registers the instance by calling tool_registry.register(t) and appends the instance to a local list. Once the loop completes it returns the list of created ToolDefinition objects.

### Parameters

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `count` = `5` | `int` | ❌ | Number of ToolDefinition instances to create and register.
<br>**Constraints:** Should be a non-negative integer (function does not validate; negative values will result in range(count) behavior which produces no iterations). |

### Returns

**Type:** `list[ToolDefinition]`

A list containing the ToolDefinition instances that were created and registered (length equals count unless count is such that the loop yields fewer iterations).


**Possible Values:**

- A list with count ToolDefinition objects when count > 0
- An empty list when count is 0 or when count causes no iterations (e.g., negative values)

### Side Effects

> ❗ **IMPORTANT**
> This function has side effects that modify state or perform I/O operations.

- Calls tool_registry.register(t) for each created ToolDefinition, mutating the global/shared tool_registry state by registering new tools
- Creates ToolDefinition instances (allocates objects) but that is standard in-memory allocation

### Usage Examples

#### Create and register 3 generated tools for use in tests

```python
_make(3)
```

Constructs three ToolDefinition objects, registers each with tool_registry, and returns the list of the three created ToolDefinition instances.

#### Use default to create and register 5 tools

```python
_make()
```

Creates five generated ToolDefinition objects, registers them in tool_registry, and returns the list.

### Complexity

Time complexity O(n) where n = count (the function performs a constant amount of work per iteration). Space complexity O(n) for the returned list of ToolDefinition objects.

### Related Functions

- `tool_registry.register` - Called by this function to register each created ToolDefinition; responsible for recording/registering the tool in the shared registry.
- `ToolDefinition.__init__` - Constructor invoked to create each tool instance with the provided generated fields.

### Notes

- The function does not validate the count parameter; passing a negative integer results in zero iterations and an empty list being returned.
- Any exceptions thrown by ToolDefinition construction or tool_registry.register will propagate out of this function because they are not caught here.
- The generated values (names, URLs, etc.) follow a predictable pattern: name 'tool-{i}', description 'Generated tool {i}', and health_check_url 'https://example.com/tool-{i}/health'.
- Because it mutates tool_registry, this helper is suitable for test setup but will affect global/shared test state.

---



#### make_events

![Type: Sync](https://img.shields.io/badge/Type-Sync-green)

### Signature

```python
def make_events() -> Callable[[int, 'EventTopic'], list['Event']]
```

### Description

Returns a factory function _make that, when called, constructs and returns a list of Event instances.


make_events is a zero-argument factory fixture that defines and returns an inner function _make. The returned _make function accepts a count and a topic and constructs a list comprehension of Event(...) objects. Each Event has source set to the constant string 'test-factory', topic set to the provided topic, action set to 'action.{i}' where i ranges from 0 to count-1, and payload set to {'index': i}. make_events does not perform any I/O or mutate external state; it only builds and returns a callable used to produce test Event objects.

### Returns

**Type:** `Callable[[int, EventTopic], list[Event]]`

A factory function (_make) that when invoked creates a list of Event objects.


**Possible Values:**

- A callable that when called as _make() returns a list of 10 Event objects (default arguments).
- A callable that when called as _make(5, some_topic) returns a list of 5 Event objects all with topic=some_topic.

### Usage Examples

#### Generate the default 10 test events using the default topic

```python
factory = make_events()
events = factory()
```

Obtains the _make factory from make_events and calls it with no args to get 10 Event instances with topic EventTopic.SYSTEM.

#### Generate 3 events with a custom topic

```python
factory = make_events()
events = factory(3, EventTopic.CUSTOM)
```

Creates 3 Event objects whose topic is EventTopic.CUSTOM; actions will be 'action.0', 'action.1', 'action.2'.

### Complexity

Time: O(n) where n is the count argument passed to the returned _make (list comprehension iterates n times). Space: O(n) for the returned list of Event objects.

### Related Functions

- `_make` - This inner function is defined inside make_events and is returned by make_events; _make is the factory used to create the list of Event objects.

### Notes

- The outer make_events has no parameters and returns the inner factory function.
- Default _make parameters are count=10 and topic=EventTopic.SYSTEM; types for Event and EventTopic come from the surrounding test codebase and are referenced but not defined in this snippet.
- No validation is performed on the count or topic arguments inside _make; passing non-integer or negative counts will behave according to Python's range() semantics (e.g., negative count yields an empty list).

---



#### _make

![Type: Sync](https://img.shields.io/badge/Type-Sync-green)

### Signature

```python
def _make(count: int = 10, topic: EventTopic = EventTopic.SYSTEM) -> list[Event]
```

### Description

Create and return a list of Event instances with sequentially numbered action names and simple payloads based on the provided count and topic.


This function constructs a list of Event objects using a list comprehension. For each integer i in range(count) it instantiates an Event with a fixed source value 'test-factory', the provided topic, an action string formatted as 'action.{i}', and a payload dictionary {'index': i}. The result is a list of count Event instances in ascending order of i.

### Parameters

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `count` = `10` | `int` | ❌ | Number of Event instances to create.
 |
| `topic` = `EventTopic.SYSTEM` | `EventTopic` | ❌ | Topic value assigned to each created Event; default is EventTopic.SYSTEM.
 |

### Returns

**Type:** `list[Event]`

A list containing count Event objects. Each Event has source='test-factory', topic set to the provided topic, action set to 'action.{i}' where i is the index in the sequence, and payload {'index': i}.


**Possible Values:**

- A list of length equal to count containing Event instances (e.g., count=3 -> [Event(action='action.0'), Event(action='action.1'), Event(action='action.2')])
- An empty list when count is 0

### Usage Examples

#### Create default 10 events with the default topic

```python
_make()
```

Returns a list of 10 Event instances with actions 'action.0' through 'action.9', payloads {'index': 0} .. {'index': 9}, and source 'test-factory'.

#### Create 3 events with a custom topic

```python
_make(3, EventTopic.CUSTOM)
```

Returns a list of 3 Event instances each having topic EventTopic.CUSTOM and actions 'action.0' .. 'action.2'.

### Complexity

Time: O(n) where n = count (each iteration constructs one Event). Space: O(n) for the returned list of Event objects.

### Related Functions

- `Event` - This function constructs and returns instances of the Event class by calling its constructor.
- `EventTopic` - Used as the type/default for the topic parameter and assigned to each Event's topic field.

### Notes

- The source field of each Event is hard-coded to the string 'test-factory'.
- The function relies on the Event constructor and EventTopic being available in scope; any errors from those are not handled here.
- No validation is performed on count (e.g., negative values are not checked) — behavior for negative counts follows Python's range function (producing an empty list).

---


