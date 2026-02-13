<details>
<summary>Documentation Metadata (click to expand)</summary>

```json
{
  "doc_type": "file_overview",
  "file_path": "tests/conftest.py",
  "source_hash": "0a8414513e75de67474a495968336058411f8033fa1fa81bd11cd32fe31ec143",
  "last_updated": "2026-02-13T16:48:17.243030+00:00",
  "tokens_used": 67961,
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

This module defines a suite of pytest fixtures used by the Super-MCP project's tests. It includes fixtures that create and manage an asyncio event loop for the entire test session, ephemeral temporary directories for file-based artifacts, pre-populated skill files in a temporary skills directory, and an exports directory. The file also supplies small, concrete sample domain objects (SkillDefinition, ToolDefinition, Event, Checkpoint, Artifact, Session) with fixed fields so tests can depend on consistent input instances. Several fixtures return fresh in-memory components used by the system under test: EventBus, SkillRegistry, ToolRegistry, SafetyLayer, Kernel (booted and shut down around each test), GameState, and GameRunner. The module also provides AsyncMock-based event callbacks and a canned mock LLM response payload for testing integrations.

In addition to single-instance fixtures, the file includes factory-style fixtures that return callables used at test time to create multiple resources: make_skills registers N generated SkillDefinition instances into the SkillRegistry (default count=5) and returns the created list; make_tools similarly registers N ToolDefinition instances into the ToolRegistry; make_events returns a list of Event instances (default count=10) and accepts an optional EventTopic. The kernel fixture is async: it constructs Kernel(), awaits boot(), yields the instance to the test, and ensures await k.shutdown() after the test. The temporary-directory fixtures rely on tempfile.TemporaryDirectory and pathlib.Path to ensure test isolation; skills_dir writes three markdown files with YAML front matter and simple content, enabling tests that read skill files from disk. Overall, this file centralizes test setup/teardown and promotes reuse of consistent test data and runtime components across the test suite.

## Dependencies

### External Dependencies

| Module | Usage |
| --- | --- |
| `pytest` | import pytest — provides the pytest.fixture decorator used on every fixture defined in this file (all functions are pytest fixtures). |

### Internal Dependencies

| Module | Usage |
| --- | --- |
| `__future__` | from __future__ import annotations — enables postponed evaluation of annotations, allowing the module to use forward references and simplify type hints for fixtures (see type hints like AsyncGenerator, Generator and return types for fixtures). |
| `asyncio` | import asyncio — used to create a new event loop for the session-scoped event_loop fixture via asyncio.new_event_loop(). |
| `tempfile` | import tempfile — used by tmp_dir fixture to create ephemeral TemporaryDirectory instances (tempfile.TemporaryDirectory) that are converted to pathlib.Path for tests that need isolated filesystem locations. |
| `pathlib` | from pathlib import Path — Path is used throughout to build and return filesystem paths (tmp_dir, skills_dir, exports_dir) and to write sample skill markdown files. |
| `typing` | from typing import AsyncGenerator, Generator — these types are used in fixture signatures for static typing (e.g., kernel: AsyncGenerator[Kernel, None], tmp_dir: Generator[Path, None, None]). |
| [unittest.mock](../unittest/mock.md) | from unittest.mock import AsyncMock — AsyncMock is used to provide an asynchronous mock callback suitable for subscribing to the EventBus in tests (mock_event_callback fixture). |
| [src.kernel.types](../src/kernel/types.md) | from src.kernel.types import (Artifact, Checkpoint, EntityID, Event, EventTopic, Session, SessionState, SkillDefinition, ToolDefinition, ToolHealth) — these type and data classes are instantiated by many fixtures (sample_skill, sample_tool, sample_event, sample_checkpoint, sample_artifact, sample_session) and used in factory helpers (make_skills/make_tools/make_events). |
| [src.kernel.event_bus](../src/kernel/event_bus.md) | from src.kernel.event_bus import EventBus — EventBus is instantiated in the event_bus fixture with buffer_size=1000 to provide an in-memory event bus for tests. |
| [src.kernel.registry](../src/kernel/registry.md) | from src.kernel.registry import SkillRegistry, ToolRegistry — used to create fresh registries in skill_registry and tool_registry fixtures and to register generated items inside make_skills and make_tools factory fixtures. |
| [src.kernel.safety](../src/kernel/safety.md) | from src.kernel.safety import SafetyLayer — SafetyLayer() is instantiated and returned by the safety_layer fixture to allow tests to use the system's safety layer with default rules. |
| [src.kernel.kernel](../src/kernel/kernel.md) | from src.kernel.kernel import Kernel — Kernel is used in the async kernel fixture: the fixture constructs Kernel(), awaits k.boot(), yields the kernel to the test, and ensures await k.shutdown() after the test completes. |
| [src.games.engine.state](../src/games/engine/state.md) | from src.games.engine.state import GameState — GameState(max_undo=50) is returned by the game_state fixture to provide a fresh game state instance for tests. |
| [src.games.engine.runner](../src/games/engine/runner.md) | from src.games.engine.runner import GameRunner — GameRunner() is returned by the game_runner fixture to provide a runner with no games registered for tests that exercise game-running logic. |

## 📁 Directory

This file is part of the **tests** directory. View the [directory index](_docs/tests/README.md) to see all files in this module.

## Architecture Notes

- Uses pytest fixture patterns to centralize and reuse test setup: fixtures provide both single-object instances (e.g., sample_skill) and factory-callable fixtures (make_skills, make_tools, make_events) which return functions that create multiple objects on demand.
- Asynchronous lifecycle handling: the event_loop fixture creates a session-scoped asyncio event loop via asyncio.new_event_loop() and closes it after the test session; the kernel fixture is async and explicitly awaits Kernel.boot() before yielding and Kernel.shutdown() after yielding to ensure proper startup/shutdown sequencing in async tests.
- Filesystem isolation: tmp_dir uses tempfile.TemporaryDirectory to ensure tests have an isolated directory; skills_dir populates a 'skills' subdirectory with three markdown files (code-review.md, security-audit.md, data-analysis.md) containing YAML front matter and a simple body, enabling tests that exercise file-based skill loading.
- Minimal error handling in fixtures: the fixtures rely on pytest and context managers (TemporaryDirectory) to handle cleanup. Tests depending on kernel or external resources should handle potential boot/shutdown failures themselves or assert expected exceptions.
- Registries and mutability: make_skills and make_tools register generated definitions into the provided registries (SkillRegistry, ToolRegistry), so tests that call these factories will mutate shared registry fixtures. Tests should be aware of fixture scope and isolation to avoid cross-test contamination.

## Usage Examples

### Testing a component that needs a booted Kernel and an EventBus subscription

In an async pytest test, declare kernel and event_bus as parameters. The kernel fixture will await Kernel.boot() before the test runs and will shut it down after the test completes. Use event_bus (an EventBus instance created with buffer_size=1000) to subscribe mock_event_callback (an AsyncMock fixture) and assert that published Event instances (for example, those created by make_events()) are delivered. Sequence: test setup uses kernel (already booted), event_bus.subscribe(mock_event_callback), publish one or more Event instances, await any asynchronous processing, then assert mock_event_callback.await_count or call arguments. After test completes, kernel.shutdown() is awaited automatically by the fixture teardown.

### Registering multiple generated skills for unit tests that exercise the SkillRegistry

In a test, use the make_skills fixture (a factory callable). Call skills = make_skills(3) to create and register three SkillDefinition objects. Each generated SkillDefinition has name f'skill-{i}', description, version '1.0.0', tags ['generated', f'batch-{i % 3}'], and empty parameters/examples. The factory calls skill_registry.register(s) for each created skill, so afterward tests can query skill_registry to verify registration and lookup behavior. Cleanup depends on fixture scopes: skill_registry fixture returns a fresh SkillRegistry instance per test (default pytest function scope), so no explicit teardown is required.

### Working with a temporary skills directory on disk

Use the skills_dir fixture to obtain a Path to a temporary directory containing three sample markdown files: code-review.md, security-audit.md, and data-analysis.md. Each file contains YAML front matter with name, version, and tags followed by a heading and body. A test that loads skill files from disk can point its loader at skills_dir and assert that the loader reads the files and parses name/version/tags from the front matter. The tmp_dir fixture ensures the directory is removed after the test via tempfile.TemporaryDirectory context manager.

## Maintenance Notes

- Kernel lifecycle: the kernel fixture awaits Kernel.boot() and Kernel.shutdown(); if Kernel.boot()/shutdown() change their signatures or become blocking long-running operations, tests may need to adapt (for example by increasing timeouts or making boot/shutdown configurable/mocked).
- Event loop management: event_loop fixture creates a new event loop for the whole test session. If individual tests need their own loop or rely on the default pytest-asyncio loop policy, adjust scope or remove this fixture to avoid conflicts.
- Registry mutation: make_skills and make_tools register entries into the provided registries. If test suite adds long-lived registries (e.g., session scope), consider clearing registries between tests to avoid cross-test interference.
- Hard-coded sample data: many fixtures return concrete sample values (e.g., sample_artifact.content, sample_event.payload). If tests require variations, consider adding additional factory fixtures or parameterizing existing ones instead of editing these common fixtures.
- Dependency updates: pytest is an external dependency; ensure tests run with a pytest version supporting the fixture features used. Internal API changes in src.kernel.* or src.games.* (constructor signatures, method names) will break these fixtures and require updates here.

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
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]
```

### Description

Provide (yield) a newly created asyncio event loop and then close it after use.


This function creates a new asyncio event loop using asyncio.new_event_loop(), yields that loop to the caller, and after the caller resumes the generator it closes the loop by calling loop.close(). The implementation is a simple generator (not an async function). There are no explicit exception handlers or additional logic.

### Returns

**Type:** `Generator[asyncio.AbstractEventLoop, None, None]`

Yields a newly created asyncio event loop object to the caller. The generator will execute loop.close() when resumed after the yield.


**Possible Values:**

- A newly created instance of an asyncio event loop (e.g., asyncio.BaseEventLoop / platform-specific loop implementation) yielded via the generator
- StopIteration after the generator completes cleanup when resumed

### Side Effects

> ❗ **IMPORTANT**
> This function has side effects that modify state or perform I/O operations.

- Creates a new asyncio event loop by calling asyncio.new_event_loop()
- Closes the created event loop by calling loop.close() when the generator continues after the yield

### Usage Examples

#### Manual use of the generator to obtain an event loop and run cleanup

```python
gen = event_loop()
loop = next(gen)
# use loop for synchronous test setup or to run coroutines
# ...
# resume the generator to perform cleanup (which calls loop.close())
try:
    next(gen)
except StopIteration:
    pass
```

Obtain the loop by advancing the generator once; after using the loop, advance the generator again to let the function execute the post-yield code that closes the loop. The second next() runs loop.close() and finishes the generator.

#### Typical pytest fixture usage (conftest.py context)

```python
@pytest.fixture(scope='session')
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()
```

When used as a pytest fixture, pytest handles advancing the generator and running the cleanup after tests that depend on the fixture complete. (The shown decorator is not present in the function body but illustrates the common surrounding usage in tests/conftest.py.)

### Complexity

O(1) time and O(1) space: the function performs a constant number of operations and allocates a single event loop object.

### Related Functions

- `asyncio.new_event_loop` - Called by this function to create the event loop
- `loop.close` - Called by this function to close the created event loop

### Notes

- This is a generator function (uses yield). To ensure loop.close() runs, callers must resume the generator after the yield (e.g., by calling next(gen) again) or rely on a framework (such as pytest fixture handling) that advances the generator to perform cleanup.
- There are no explicit raise statements in the implementation; any exceptions would originate from the called asyncio functions but are not handled here.
- The code snippet assumes asyncio is available and imported in the module scope (not shown in the snippet).

---



#### tmp_dir

![Type: Sync](https://img.shields.io/badge/Type-Sync-green) ![Generator: Yes](https://img.shields.io/badge/Generator-Yes-purple)

### Signature

```python
def tmp_dir() -> Generator[Path, None, None]
```

### Description

Provide a generator that yields a pathlib.Path pointing to a newly created temporary directory created via tempfile.TemporaryDirectory.


This function is a generator that creates a temporary directory using tempfile.TemporaryDirectory with prefix 'smcp_test_'. Inside the context manager it yields a Path object (from pathlib.Path) constructed from the temporary directory path string. The TemporaryDirectory context manager ensures the directory exists for the duration while the generator is paused at the yield; when the generator is finalized (context is exited), the temporary directory is removed by tempfile.TemporaryDirectory's cleanup.

### Returns

**Type:** `Generator[Path, None, None]`

A generator that yields a single pathlib.Path referring to the created temporary directory. The directory exists while the generator is paused at the yield; cleanup happens when the generator/context is exited.


**Possible Values:**

- A pathlib.Path object pointing to an existing temporary directory (string path wrapped in Path) while the generator is active
- No value (generator completes) after the yield and cleanup; the directory is removed by the context manager

### Raises

| Exception | Condition |
| --- | --- |
| `OSError` | If tempfile.TemporaryDirectory fails to create the temporary directory (propagated from the underlying call) |

### Side Effects

> ❗ **IMPORTANT**
> This function has side effects that modify state or perform I/O operations.

- Creates a temporary directory on the filesystem via tempfile.TemporaryDirectory
- Deletes (cleans up) the temporary directory when the generator/context is exited

### Usage Examples

#### Direct iteration over the generator to obtain a temporary directory path and ensure cleanup when done

```python
gen = tmp_dir()
path = next(gen)  # yields a pathlib.Path to the created temp dir
# use path for filesystem operations while directory exists
try:
    pass  # perform work using path
finally:
    # finalizing the generator (or letting it go out of scope) triggers exit of the context and cleanup
    gen.close()
```

Demonstrates getting the Path from the generator and ensuring the TemporaryDirectory context is exited (gen.close()) so the directory is removed.

#### Using the generator as a pytest-style fixture (typical placement under tests/conftest.py)

```python
# In pytest this function is commonly used as a fixture that yields a Path to a temporary directory
# test receives the Path and the directory is removed after the test finishes
```

Shows the typical test usage pattern: the yielded Path is available during the test and is cleaned up automatically when the fixture/generator finalizes.

### Complexity

Time complexity: O(1) to create and yield the path (cost dominated by OS call to create directory). Space complexity: O(1) additional Python memory; filesystem storage proportional to any files created by the caller inside the temporary directory.

### Related Functions

- `tempfile.TemporaryDirectory` - This function directly uses tempfile.TemporaryDirectory as the mechanism to create and clean up the temporary directory.
- `pathlib.Path` - Path is used to wrap the temporary directory string returned by TemporaryDirectory before yielding.

### Notes

- The function yields once and relies on the TemporaryDirectory context manager to perform cleanup when the generator completes or is closed.
- There is no explicit decorator in the shown implementation; if intended for pytest fixtures it would normally be decorated with @pytest.fixture in conftest.py.
- If the generator is not closed or exhausted, the TemporaryDirectory cleanup will not run immediately; relying on garbage collection to finalize may delay cleanup.

---



#### skills_dir

![Type: Sync](https://img.shields.io/badge/Type-Sync-green)

### Signature

```python
def skills_dir(tmp_dir: Path) -> Path
```

### Description

Create a 'skills' subdirectory inside the provided temporary directory and populate it with three sample Markdown skill files, then return the path to that subdirectory.


Given a Path object tmp_dir, the function creates a subdirectory named 'skills' (tmp_dir / 'skills'), then iterates over a fixed tuple of three skill base names ('code-review', 'security-audit', 'data-analysis'). For each name it writes a corresponding Markdown file named '<name>.md' into the skills directory containing YAML front matter (name, version, tags) and a simple Markdown body with a title derived from the name and the text 'Test skill.' Finally it returns the Path to the created 'skills' directory.

### Parameters

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `tmp_dir` | `Path` | ✅ | Path to an existing directory (typically a temporary directory) under which a 'skills' subdirectory will be created.
<br>**Constraints:** Must be a pathlib.Path instance (or compatible object supporting / operator and write operations), Should exist and be a directory or at least allow creation of a subdirectory, Must be writable by the process (permissions required to create subdirectory and files) |

### Returns

**Type:** `Path`

A pathlib.Path pointing to the created 'skills' subdirectory containing the generated Markdown files.


**Possible Values:**

- A Path object representing tmp_dir / 'skills' when creation and writes succeed
- Function may not return if an exception occurs during directory creation or file writes

### Raises

| Exception | Condition |
| --- | --- |
| `FileExistsError` | Raised by sd.mkdir() if a 'skills' entry already exists and is not a directory (or if mkdir is called without exist_ok and an entry exists). |
| `OSError` | Raised on underlying filesystem errors during directory creation or file writes (including PermissionError, disk full, invalid path). |

### Side Effects

> ❗ **IMPORTANT**
> This function has side effects that modify state or perform I/O operations.

- Creates a directory: tmp_dir / 'skills' (filesystem)
- Writes three files to the filesystem: '<name>.md' for each of 'code-review', 'security-audit', 'data-analysis' inside the created directory

### Usage Examples

#### In a pytest fixture or test that needs a pre-populated skills directory

```python
sd = skills_dir(tmp_path)
# sd is a Path to the created directory containing code-review.md, security-audit.md, data-analysis.md
```

Demonstrates calling the function with a temporary Path (e.g., pytest tmp_path) and using the returned Path to access generated sample skill files.

### Complexity

Time complexity O(n) where n is the number of skill names written (here n=3, so effectively constant). Space complexity O(n) in terms of number of files created; each file consumes disk space proportional to its content size (constant-sized content in this implementation).

### Related Functions

- `tmp_path` - Common pytest fixture used as the temporary directory argument when calling this helper; provides the tmp_dir Path typically passed to this function

### Notes

- The list of skill names is hard-coded to ('code-review', 'security-audit', 'data-analysis').
- sd.mkdir() is called without exist_ok=True, so if the 'skills' path already exists an exception may be raised.
- Content of each file includes a YAML-like front matter block and a Markdown title generated by replacing hyphens with spaces and title-casing the name.
- The function relies on Path.write_text and Path.mkdir behaviors from pathlib; any exceptions from those calls propagate to the caller.

---



#### exports_dir

![Type: Sync](https://img.shields.io/badge/Type-Sync-green)

### Signature

```python
def exports_dir(tmp_dir: Path) -> Path
```

### Description

Create a subdirectory named 'exports' inside the provided tmp_dir and return its Path.


Given a Path object tmp_dir, the function computes a child path by appending the string 'exports' (tmp_dir / "exports"), creates that directory using Path.mkdir() with default options, and returns the Path to the created directory. The function does not set exist_ok or parents on mkdir(), so it expects the parent tmp_dir to exist and that the 'exports' directory does not already exist unless the caller is prepared to handle the exception.

### Parameters

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `tmp_dir` | `Path` | ✅ | The base directory under which an 'exports' subdirectory will be created.
<br>**Constraints:** Must be a pathlib.Path (or objects supporting division operator to produce a Path-like result)., tmp_dir must exist on the filesystem and be writable, because mkdir() is called without parents=True., If tmp_dir does not exist or is not writable, mkdir() will raise an OSError (or subclass). |

### Returns

**Type:** `Path`

Path object pointing to the newly created 'exports' subdirectory (tmp_dir/'exports').


**Possible Values:**

- A pathlib.Path instance referencing the created directory at tmp_dir/'exports'.

### Raises

| Exception | Condition |
| --- | --- |
| `FileExistsError` | Raised by Path.mkdir() if the 'exports' path already exists and mkdir() is called with default exist_ok=False. |
| `OSError` | Raised by Path.mkdir() for filesystem-related errors (e.g., permission denied, parent directory does not exist, invalid path). |

### Side Effects

> ❗ **IMPORTANT**
> This function has side effects that modify state or perform I/O operations.

- Creates a directory on the filesystem at the path tmp_dir / 'exports' via Path.mkdir()

### Usage Examples

#### Create an exports directory inside a temporary directory (e.g., in tests)

```python
ed = exports_dir(tmp_path)
# ed is tmp_path / 'exports', and the directory now exists on disk
```

Demonstrates creating the 'exports' subdirectory under an existing temporary directory and obtaining its Path for further file operations.

### Complexity

O(1) time complexity and O(1) additional space complexity (constant-time path construction and a single filesystem mkdir call).

### Related Functions

- `Path.mkdir` - Calls: exports_dir invokes Path.mkdir() to create the directory on disk.

### Notes

- Because mkdir() is called without exist_ok=True, calling exports_dir when tmp_dir/'exports' already exists will raise FileExistsError.
- The function does not create missing parent directories (parents=False by default), so tmp_dir must exist prior to calling this function.
- This function performs real filesystem I/O; in tests, use fixtures that provide an isolated temporary Path (e.g., pytest's tmp_path/tmpdir) to avoid side effects on real data.

---



#### sample_skill

![Type: Sync](https://img.shields.io/badge/Type-Sync-green)

### Signature

```python
def sample_skill() -> SkillDefinition
```

### Description

Return a minimal SkillDefinition instance pre-populated with fixed test data.


The function constructs and returns a SkillDefinition object with hard-coded values intended for tests. It sets the name, description, version, tags, a single parameter schema entry, and a single example input/output pair. There is no computation or branching — the function always returns the same SkillDefinition instance contents each time it is called.

### Returns

**Type:** `SkillDefinition`

A SkillDefinition instance created with static test values: name 'test-skill', description 'A skill used in tests', version '1.0.0', tags ['test','fixture'], parameters list with one parameter {'name': 'input', 'type': 'string', 'required': True}, and examples list with one example {'input': 'hello', 'output': 'world'}.


**Possible Values:**

- A SkillDefinition object configured with the specific test data described above

### Usage Examples

#### Obtain a reusable minimal SkillDefinition for unit tests or fixtures

```python
skill = sample_skill()
# use `skill` in assertions or pass to functions that accept SkillDefinition
```

Demonstrates calling the function to get the predefined SkillDefinition instance for use in tests.

### Complexity

O(1) time and O(1) space — the function performs a single object construction with a fixed small number of literal fields.

### Related Functions

- `SkillDefinition` - Constructed by this function; the returned object is an instance of SkillDefinition.

### Notes

- All returned values are constant literals defined in the function body.
- No validation, mutation, I/O, or external calls are performed — the function purely constructs and returns an object.
- The function relies on SkillDefinition being available in scope where this function is defined (imported or declared).

---



#### sample_tool

![Type: Sync](https://img.shields.io/badge/Type-Sync-green)

### Signature

```python
def sample_tool() -> ToolDefinition
```

### Description

Return a ToolDefinition instance pre-populated with fixed test values.


This function constructs and returns a ToolDefinition object with a fixed set of attributes intended for use in tests. The returned object has hard-coded values for name, description, category, authentication settings, health check URL, health status, version, and tags. There is no conditional logic, iteration, or external I/O; the function simply instantiates ToolDefinition with the listed literal values and returns it.

### Returns

**Type:** `ToolDefinition`

A ToolDefinition object initialized with specific test-oriented values.


**Possible Values:**

- ToolDefinition(name='test-tool', description='A tool used in tests', category='testing', auth_required=False, auth_scopes=[], health_check_url='https://httpbin.org/get', health=ToolHealth.HEALTHY, version='1.0.0', tags=['test', 'fixture'])

### Usage Examples

#### Obtain a standard tool fixture for unit tests

```python
tool = sample_tool()
```

Creates and returns a ToolDefinition instance pre-filled with the test values shown in the implementation; useful as a fixture in tests.

### Complexity

O(1) time complexity and O(1) space complexity (constant-time object instantiation and return).

### Related Functions

- `ToolDefinition` - Constructor/class used to create the returned object
- `ToolHealth.HEALTHY` - Enumerated value referenced to set the health field on the returned object

### Notes

- Function has no parameters and always returns the same ToolDefinition instance shape with literal values.
- No validation, I/O, or side effects are performed; if ToolDefinition's constructor raises, that would propagate but the function itself contains no raise statements.
- This is suitable as a test fixture; changing the returned literals will change tests that depend on them.

---



#### sample_event

![Type: Sync](https://img.shields.io/badge/Type-Sync-green)

### Signature

```python
def sample_event() -> Event
```

### Description

Return a minimal Event instance pre-filled with test values.


This function constructs and returns an Event object populated with a fixed set of fields intended for testing: source set to the string "test", topic set to EventTopic.SYSTEM, action set to "test.action", and payload set to a dictionary {"key": "value"}. The function takes no inputs and always returns the same Event instance structure.

### Returns

**Type:** `Event`

An Event instance with the following fields: source="test", topic=EventTopic.SYSTEM, action="test.action", payload={"key": "value"}.


**Possible Values:**

- Event(source='test', topic=EventTopic.SYSTEM, action='test.action', payload={'key': 'value'})

### Usage Examples

#### Create a reusable minimal Event for tests

```python
evt = sample_event()
```

Demonstrates calling sample_event to obtain a preconfigured Event instance for assertions in tests.

#### Accessing fields of the test Event

```python
evt = sample_event()
assert evt.source == 'test'
assert evt.action == 'test.action'
```

Shows typical usage in a unit test to verify the returned Event's attributes.

### Complexity

O(1) time and O(1) additional space — constructs and returns a single Event object with fixed-size payload.

### Related Functions

- `Event` - The return type; sample_event constructs and returns an instance of Event.
- `EventTopic` - Enumeration/constant used to set the topic field on the returned Event (uses EventTopic.SYSTEM).

### Notes

- The function depends on Event and EventTopic names being available in scope (imported or defined in the module).
- No validation is performed; values are hard-coded for testing purposes.
- Because the payload is a dictionary literal, callers receive a separate object each call (mutable), so modifying evt.payload will not affect future calls.

---



#### sample_checkpoint

![Type: Sync](https://img.shields.io/badge/Type-Sync-green)

### Signature

```python
def sample_checkpoint() -> Checkpoint
```

### Description

Returns a minimal Checkpoint instance pre-populated for testing.


This function constructs and returns a Checkpoint object literal with fixed fields suitable for use in tests. It creates a Checkpoint with name set to "test-checkpoint" and state set to a dictionary containing a numeric counter (42) and a list of items ["a", "b"]. The function performs no calculations or branching; it simply calls the Checkpoint constructor with these literal values and returns the resulting object.

### Returns

**Type:** `Checkpoint`

An instance of the Checkpoint class constructed with predefined test values.


**Possible Values:**

- Checkpoint(name='test-checkpoint', state={'counter': 42, 'items': ['a', 'b']})

### Usage Examples

#### Create a reusable minimal checkpoint fixture in tests

```python
cp = sample_checkpoint()
```

Demonstrates obtaining the predefined Checkpoint instance for assertions or as a fixture input.

### Complexity

O(1) time and O(1) extra space — performs a single constructor call and returns the created object.

### Related Functions

- `Checkpoint` - Constructed by and returned (the function calls the Checkpoint constructor to create the returned object).

### Notes

- The function assumes the Checkpoint class/type is available in scope (imported or defined elsewhere).
- No validation is performed on the values; they are fixed literals intended for tests.

---



#### sample_artifact

![Type: Sync](https://img.shields.io/badge/Type-Sync-green)

### Signature

```python
def sample_artifact(tmp_dir: Path) -> Artifact
```

### Description

Returns a minimal Artifact instance constructed with fixed test values.


The function constructs and returns an Artifact object with hard-coded values for name, content, format, and tags. The provided parameter tmp_dir is accepted but not used in the implementation. No conditional logic or side effects occur; the function always returns the same Artifact shape (with the same field values) when called.

### Parameters

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `tmp_dir` | `Path` | ✅ | A Path parameter accepted by the fixture; not used in the function body.
<br>**Constraints:** No constraints enforced by this function (value is not accessed or validated). |

### Returns

**Type:** `Artifact`

An Artifact instance constructed with fixed test data: name='test-artifact', content='# Test Artifact\n\nHello, world.\n', format='md', tags=['test'].


**Possible Values:**

- An Artifact object with the exact fields: name='test-artifact', content='# Test Artifact\n\nHello, world.\n', format='md', tags=['test']

### Usage Examples

#### Obtain a simple test Artifact in unit tests

```python
artifact = sample_artifact(tmp_dir)
```

Demonstrates calling the fixture to get a minimal Artifact instance; tmp_dir is passed but not used.

### Complexity

O(1) time complexity and O(1) space complexity — the function performs a single object construction with constant-sized literals.

### Notes

- The tmp_dir parameter is unused in the implementation — it may exist to satisfy a pytest fixture signature or future use.
- The function always returns the same content and metadata; it does not read or write files or depend on external state.

---



#### sample_session

![Type: Sync](https://img.shields.io/badge/Type-Sync-green)

### Signature

```python
def sample_session() -> Session
```

### Description

Returns a newly constructed Session instance with its state set to SessionState.RUNNING.


This function constructs and returns a Session object by calling the Session constructor with a single keyword argument: state=SessionState.RUNNING. It does not take any parameters, perform any computation, or modify external state; it simply returns the created Session instance.

### Returns

**Type:** `Session`

A Session instance created with its state set to SessionState.RUNNING.


**Possible Values:**

- Session(state=SessionState.RUNNING)

### Usage Examples

#### Create a minimal running session for tests

```python
sample_session()
```

Demonstrates calling the helper to obtain a Session object that is already in the RUNNING state for use in test fixtures or assertions.

### Complexity

O(1) time and O(1) space - constant-time construction and return of a Session object.

### Related Functions

- `Session` - Constructor used by this function to create and return the session instance
- `SessionState` - Enumeration/namespace used to set the session's state to RUNNING

### Notes

- The function body is a single return statement; it does not validate inputs (there are none) or handle exceptions.
- The concrete behavior depends on the Session constructor and SessionState enum; this function only forwards a specific state value to Session.

---



#### event_bus

![Type: Sync](https://img.shields.io/badge/Type-Sync-green)

### Signature

```python
def event_bus() -> EventBus
```

### Description

A fresh EventBus instance.

This function constructs and returns a new EventBus object by calling the EventBus constructor with buffer_size set to 1000. The function has no parameters and performs a single object instantiation before returning that instance.

### Returns

**Type:** `EventBus`

A newly constructed EventBus instance created by calling EventBus(buffer_size=1000).


**Possible Values:**

- An EventBus instance configured with buffer_size=1000

### Usage Examples

#### Obtain a fresh EventBus instance for use in tests or local code

```python
bus = event_bus()
```

Creates and returns a new EventBus object initialized with buffer_size=1000.

### Complexity

O(1) time and O(1) additional space (constant-time object construction; actual constructor complexity depends on EventBus.__init__).

### Related Functions

- `EventBus` - Calls the EventBus constructor (EventBus(buffer_size=1000)) to create the returned instance

### Notes

- The function's docstring is exactly 'A fresh EventBus instance.'
- Any exceptions or side effects originating from EventBus.__init__ are not visible in this implementation and are therefore not documented here.

---



#### skill_registry

![Type: Sync](https://img.shields.io/badge/Type-Sync-green)

### Signature

```python
def skill_registry() -> SkillRegistry
```

### Description

Returns a newly constructed SkillRegistry instance by calling its constructor.


This function is a zero-argument factory/helper that creates and returns a fresh SkillRegistry object by invoking SkillRegistry(). The implementation consists solely of a return statement that constructs and returns the object; there is no additional logic, configuration, or mutation in this function.

### Returns

**Type:** `SkillRegistry`

A newly constructed instance of the SkillRegistry class created by calling SkillRegistry().


**Possible Values:**

- An instance of SkillRegistry (the result of calling SkillRegistry()).

### Usage Examples

#### Obtain a fresh SkillRegistry for tests or setup

```python
registry = skill_registry()
```

Demonstrates creating a new SkillRegistry instance using this helper function; no arguments are required.

### Complexity

O(1) time complexity and O(1) space complexity (constructing a single object).

### Related Functions

- `SkillRegistry` - Constructs an instance of this class by calling its constructor.

### Notes

- The function relies on SkillRegistry being available in scope where this function is defined.
- No validation, caching, or singleton behavior is implemented—each call returns a new instance.

---



#### tool_registry

![Type: Sync](https://img.shields.io/badge/Type-Sync-green)

### Signature

```python
def tool_registry() -> ToolRegistry
```

### Description

Returns a newly constructed ToolRegistry instance.

The function calls the ToolRegistry constructor with no arguments and returns the resulting instance. It performs no additional computation, configuration, or mutation; it simply creates and returns a fresh ToolRegistry object.

### Returns

**Type:** `ToolRegistry`

A newly created instance of the ToolRegistry class, constructed by calling ToolRegistry().


**Possible Values:**

- An instance of ToolRegistry constructed by ToolRegistry()

### Usage Examples

#### Obtain a fresh registry for tests or initialization

```python
r = tool_registry()
```

Constructs and returns a new ToolRegistry instance for use by the caller.

### Complexity

O(1) time complexity and O(1) space complexity (aside from the space used by the returned object).

### Related Functions

- `ToolRegistry` - Constructs and returns an instance of this class (calls its constructor).

### Notes

- The function does not accept parameters and does not perform any validation.
- Any exceptions raised would originate from the ToolRegistry() constructor; this function does not explicitly raise exceptions.

---



#### safety_layer

![Type: Sync](https://img.shields.io/badge/Type-Sync-green)

### Signature

```python
def safety_layer() -> SafetyLayer
```

### Description

Return a newly constructed SafetyLayer instance using its default constructor.


This function calls the SafetyLayer constructor with no arguments and returns the resulting object. There is no additional logic, parameter handling, or mutation; it simply wraps the SafetyLayer() call in a zero-argument helper function.

### Returns

**Type:** `SafetyLayer`

A new SafetyLayer instance created by calling SafetyLayer() with no arguments.


**Possible Values:**

- An instance of SafetyLayer constructed via SafetyLayer()

### Usage Examples

#### Obtain a default SafetyLayer for tests or setup

```python
layer = safety_layer()
```

Creates and returns a new SafetyLayer instance using its default constructor.

### Complexity

O(1) time and O(1) space — the function performs a single constructor call and returns the result.

### Related Functions

- `SafetyLayer` - Constructor that is called by this function; the returned object is an instance of this class.

### Notes

- The function assumes SafetyLayer is available in the current scope (imported or defined).
- No validation or customization of the SafetyLayer instance is performed here; callers must configure the instance if needed.

---



#### async 

![Type: Async](https://img.shields.io/badge/Type-Async-blue) ![Generator: Yes](https://img.shields.io/badge/Generator-Yes-purple)

### Signature

```python
async def kernel() -> AsyncGenerator[Kernel, None]
```

### Description

Creates and yields a booted Kernel instance for use by the caller, then shuts it down after use.


This asynchronous generator constructs a Kernel instance, awaits its boot() coroutine to initialize it, yields that Kernel instance to the caller, and after the caller resumes the generator it awaits the Kernel.shutdown() coroutine to perform teardown. It is written as an async generator that ensures boot is completed before yielding and shutdown is executed after the consumer is done with the yielded Kernel.

### Returns

**Type:** `AsyncGenerator[Kernel, None]`

An async generator that yields a single Kernel instance. The generator yields the booted Kernel, and once the consumer finishes iteration/control returns to the generator, it awaits shutdown and then completes.


**Possible Values:**

- Yields a Kernel instance (the booted Kernel)
- Generator completes after shutdown, returning None

### Side Effects

> ❗ **IMPORTANT**
> This function has side effects that modify state or perform I/O operations.

- Instantiates a Kernel object (calls Kernel())
- Calls and awaits Kernel.boot(), which may mutate Kernel/internal state
- Calls and awaits Kernel.shutdown(), which may perform teardown and mutate state

### Usage Examples

#### Use as a test fixture to obtain a ready Kernel for the duration of a test

```python
async for k in kernel():
    # use k inside test
    pass
```

Demonstrates obtaining the booted Kernel from the async generator; after the test finishes using k, control returns and kernel() will await k.shutdown().

#### Use directly with 'async with' style via context manager helper (if adapted)

```python
# If adapted to an async context manager wrapper
async with kernel() as k:
    # use k
    pass
```

Shows intended lifecycle: k is available inside the block after boot(), and shutdown() runs afterward. (Note: the function as written is an async generator, not an async context manager; this example assumes an adapter.)

### Complexity

Time complexity: O(1) for the Python-level operations performed here (object construction and awaiting two coroutines). Space complexity: O(1) additional Python-level memory; the Kernel instance itself consumes memory dependent on Kernel implementation.

### Related Functions

- `Kernel.__init__` - Called to construct the Kernel instance
- `Kernel.boot` - Called and awaited to initialize the Kernel before yielding
- `Kernel.shutdown` - Called and awaited after yielding to teardown the Kernel

### Notes

- This function is an async generator that yields exactly once (the booted Kernel) and performs teardown after the consumer resumes the generator.
- No explicit exception handling is present; exceptions raised by Kernel(), Kernel.boot(), or Kernel.shutdown() will propagate to the caller.
- Defined in tests/conftest.py, indicating intended use as a test fixture.

---



#### game_state

![Type: Sync](https://img.shields.io/badge/Type-Sync-green)

### Signature

```python
def game_state() -> GameState
```

### Description

Returns a newly constructed GameState instance configured with max_undo=50.


This function creates and returns a new GameState object by calling the GameState constructor with a single keyword argument max_undo set to 50. The function has no parameters and performs no additional logic, validation, or side effects beyond instantiating and returning the object.

### Returns

**Type:** `GameState`

A newly created GameState instance constructed with max_undo=50.


**Possible Values:**

- An instance of GameState configured with max_undo equal to 50

### Usage Examples

#### Obtain a fresh GameState object for use in tests or initialization code

```python
state = game_state()
```

Demonstrates calling the function to receive a new GameState instance configured with max_undo=50.

### Complexity

Time complexity: O(1). Space complexity: O(1) (creates a single object reference).

### Notes

- The function simply wraps the GameState constructor with max_undo=50; no other behavior is implemented here.
- Implementation is minimal and visible in the provided source: return GameState(max_undo=50).

---



#### game_runner

![Type: Sync](https://img.shields.io/badge/Type-Sync-green)

### Signature

```python
def game_runner() -> GameRunner
```

### Description

Return a newly constructed GameRunner instance.

This function has no parameters and returns the result of calling the GameRunner constructor. The implementation consists of a single return statement that constructs and returns a GameRunner object. There is no additional logic, branching, or parameter handling in this function; it simply instantiates and returns GameRunner.

### Returns

**Type:** `GameRunner`

A newly created GameRunner object produced by calling GameRunner().


**Possible Values:**

- An instance of GameRunner (the object returned by GameRunner())

### Usage Examples

#### Obtain a fresh GameRunner instance for tests or initialization

```python
runner = game_runner()
```

Calls the function which returns a newly constructed GameRunner instance.

### Complexity

O(1) time complexity and O(1) space complexity (ignoring the complexity of GameRunner.__init__ which is not visible here).

### Related Functions

- `GameRunner` - Called by / constructed within this function (game_runner returns GameRunner()).

### Notes

- The function body is a single constructor call and return. Any side effects or exceptions that may occur depend solely on GameRunner's constructor implementation, which is not visible here.
- Although located in tests/conftest.py (commonly used for pytest fixtures), there is no decorator or fixture marker visible in this implementation; it is a plain function as shown.

---



#### mock_event_callback

![Type: Sync](https://img.shields.io/badge/Type-Sync-green)

### Signature

```python
def mock_event_callback() -> AsyncMock
```

### Description

Returns a newly constructed AsyncMock instance by calling AsyncMock().


This function has no parameters and, when invoked, constructs and returns a new AsyncMock object by calling AsyncMock() and returning it. There is no additional logic, branching, or mutation; the function simply acts as a small factory/wrapper around the AsyncMock constructor.

### Returns

**Type:** `AsyncMock`

A freshly created AsyncMock instance (the value produced by calling AsyncMock()).


**Possible Values:**

- An instance of AsyncMock (constructed by AsyncMock()).

### Usage Examples

#### Provide a mock asynchronous callback for subscribing to an event bus in tests

```python
cb = mock_event_callback()
# cb is an AsyncMock and can be awaited or inspected for calls in test assertions
```

Demonstrates creating the AsyncMock via the helper and using it as an async-compatible callback in tests.

### Complexity

O(1) time and O(1) space — constructs and returns a single object.

### Related Functions

- `AsyncMock` - This function calls the AsyncMock constructor and returns its result; AsyncMock is the underlying object produced.

### Notes

- The implementation directly calls AsyncMock() and returns it; the symbol AsyncMock must be imported or available in the module where this function is defined.
- The function itself is synchronous (normal def) even though it returns an async-capable mock object.

---



#### mock_llm_response

![Type: Sync](https://img.shields.io/badge/Type-Sync-green)

### Signature

```python
def mock_llm_response() -> dict
```

### Description

Returns a hard-coded dictionary representing a mock LLM response payload for tests.


This function constructs and returns a static Python dict that mimics the structure of a language model response. The returned dict contains top-level keys 'id', 'model', 'choices', and 'usage'. 'choices' is a list with a single choice dict that includes 'index', 'message' (with 'role' and 'content'), and 'finish_reason'. 'usage' is a dict with token counts. The function performs no computation beyond creating and returning this literal structure.

### Returns

**Type:** `dict`

A dictionary containing a mock LLM response payload with keys: 'id' (str), 'model' (str), 'choices' (list of choice dicts), and 'usage' (dict of token counts).


**Possible Values:**

- {"id": "mock-response-001", "model": "test-model", "choices": [{"index": 0, "message": {"role": "assistant", "content": "This is a mock response for testing."}, "finish_reason": "stop"}], "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30}}

### Usage Examples

#### Use in unit tests to simulate an LLM response without making network calls

```python
response = mock_llm_response()
```

Demonstrates calling the function to obtain the static mock payload for assertions in tests.

### Complexity

O(1) time complexity and O(1) space complexity (returns a fixed-size literal structure).

### Notes

- The function returns a static literal and does not depend on external state or inputs.
- Intended for tests (file is tests/conftest.py) to provide a predictable LLM-like payload.

---



#### make_skills

![Type: Sync](https://img.shields.io/badge/Type-Sync-green)

### Signature

```python
def make_skills(skill_registry: SkillRegistry) -> Callable[[int], list[SkillDefinition]]
```

### Description

Return a factory function that creates, registers, and returns a batch of SkillDefinition instances.


make_skills takes a SkillRegistry object and returns an inner factory function _make. When called, _make creates a specified number (default 5) of SkillDefinition instances with generated name, description, version, tags, parameters, and examples. Each created SkillDefinition is registered with the provided skill_registry via skill_registry.register(s) and appended to a list which is returned to the caller.

### Parameters

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `skill_registry` | `SkillRegistry` | ✅ | Registry object used to register each generated SkillDefinition. The function calls skill_registry.register(s) for each generated skill.
<br>**Constraints:** Must provide a register(skill: SkillDefinition) method that accepts SkillDefinition instances, Registry behavior and side effects depend on implementation of SkillRegistry.register |

### Returns

**Type:** `Callable[[int], list[SkillDefinition]]`

A factory function _make(count: int = 5) that creates count SkillDefinition objects, registers each with the provided skill_registry, and returns the list of created SkillDefinition instances.


**Possible Values:**

- A callable that when invoked returns a list of SkillDefinition objects
- The returned list length equals the count argument passed to the callable (default 5)

### Side Effects

> ❗ **IMPORTANT**
> This function has side effects that modify state or perform I/O operations.

- Calls skill_registry.register(s) for each created SkillDefinition, which mutates or updates the external skill_registry state

### Usage Examples

#### Create and register 3 generated skills in a test registry

```python
factory = make_skills(test_registry)
skills = factory(3)
```

Demonstrates obtaining the factory from make_skills and using it to create and register three SkillDefinition instances; skills is a list of the created objects.

#### Use default count to create 5 skills

```python
factory = make_skills(test_registry)
default_skills = factory()
```

Shows calling the returned factory with no arguments to create and register the default of 5 skills.

### Complexity

Time: O(n) where n is the count passed to the returned factory (creates and registers n skills). Space: O(n) additional space for the returned list of SkillDefinition objects.

### Related Functions

- `SkillRegistry.register` - Called by the factory; used to register each created SkillDefinition
- `SkillDefinition.__init__` - Called when creating each SkillDefinition instance

### Notes

- The generated SkillDefinition fields are deterministic in this implementation: name 'skill-{i}', description 'Generated skill {i}', version '1.0.0', tags ['generated', f'batch-{i % 3}'], and empty parameters/examples lists.
- No validation or error handling is implemented in make_skills; exceptions from SkillDefinition construction or skill_registry.register will propagate to the caller.
- The factory does not persist beyond calling skill_registry.register; persistence depends on the registry implementation.

---



#### _make

![Type: Sync](https://img.shields.io/badge/Type-Sync-green)

### Signature

```python
def _make(count: int = 5) -> list[SkillDefinition]
```

### Description

Creates a list of SkillDefinition instances (default 5), registers each with skill_registry, and returns the list of created SkillDefinition objects.


The function initializes an empty list named skills, then iterates count times (0..count-1). For each iteration index i it constructs a SkillDefinition instance with fields: name set to f"skill-{i}", description set to f"Generated skill {i}", version "1.0.0", tags containing "generated" and a batch tag based on i % 3, and empty parameters and examples lists. Each created SkillDefinition is registered by calling skill_registry.register(s) and appended to the local skills list. After the loop completes the function returns the list of created SkillDefinition objects.

### Parameters

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `count` = `5` | `int` | ❌ | Number of SkillDefinition instances to create and register.
<br>**Constraints:** Expected to be an integer (used with range()). If count is 0 or negative, the function will return an empty list., No explicit validation is performed in the function. |

### Returns

**Type:** `list[SkillDefinition]`

A list containing the SkillDefinition instances that were created and registered; list length equals count (or 0 if count <= 0).


**Possible Values:**

- A list of SkillDefinition objects of length count when count > 0
- An empty list when count is 0 or negative

### Side Effects

> ❗ **IMPORTANT**
> This function has side effects that modify state or perform I/O operations.

- Calls skill_registry.register(s) for each created SkillDefinition, modifying the external skill_registry state (registration side effect).

### Usage Examples

#### Create and register the default number of skills (5)

```python
_make()
```

Creates 5 SkillDefinition objects, registers each with skill_registry, and returns the list of those objects.

#### Create and register a custom number of skills

```python
_make(3)
```

Creates 3 SkillDefinition objects (skill-0, skill-1, skill-2), registers them, and returns the list.

#### Request zero skills

```python
_make(0)
```

Returns an empty list and does not call skill_registry.register because the loop does not execute.

### Complexity

Time complexity: O(n) where n = count (constructs and registers count items). Space complexity: O(n) for the returned list of SkillDefinition instances.

### Related Functions

- `skill_registry.register` - Called by _make to register each newly created SkillDefinition instance.
- `SkillDefinition` - Constructor invoked to create each skill object appended to the returned list.

### Notes

- The function relies on the presence of skill_registry and SkillDefinition in the module/global scope; these are not defined within the function.
- No input validation is done on count; non-integer or non-numeric values passed to count will cause built-in errors when used with range().
- Tags include a generated batch tag based on i % 3 producing repeating batch-0, batch-1, batch-2 patterns.

---



#### make_tools

![Type: Sync](https://img.shields.io/badge/Type-Sync-green)

### Signature

```python
def make_tools(tool_registry: ToolRegistry) -> Callable[[int], list[ToolDefinition]]
```

### Description

Factory fixture that returns a callable which registers a number of generated ToolDefinition instances in the provided ToolRegistry and returns them as a list.


make_tools accepts a ToolRegistry instance and returns an inner factory function _make. When _make(count: int = 5) is called it: 1) constructs `count` ToolDefinition objects with deterministic fields (name, description, category, auth_required, auth_scopes, health_check_url, health, version, tags) where the index i is used to generate unique values; 2) registers each created ToolDefinition with the provided tool_registry by calling tool_registry.register(t); and 3) collects and returns the created ToolDefinition objects in a list. The default number of tools created is 5 if no count is passed.

### Parameters

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `tool_registry` | `ToolRegistry` | ✅ | The registry object into which each generated ToolDefinition will be registered via its register(...) method.
<br>**Constraints:** Must provide an object with a .register(...) method that accepts a ToolDefinition, No internal validation is performed on tool_registry by this function |

### Returns

**Type:** `Callable[[int], list[ToolDefinition]]`

A factory function _make that when called with an integer count creates `count` ToolDefinition instances, registers each with the supplied tool_registry, and returns a list of the created ToolDefinition objects.


**Possible Values:**

- A callable. When invoked with count n (default 5) returns a list of n ToolDefinition objects.
- Returned list length equals the provided count (integer >= 0).

### Side Effects

> ❗ **IMPORTANT**
> This function has side effects that modify state or perform I/O operations.

- Calls tool_registry.register(t) for each generated ToolDefinition, mutating the external tool_registry state by registering new tools

### Usage Examples

#### Create and register 5 generated tools (default)

```python
factory = make_tools(my_tool_registry)
created_tools = factory()
# created_tools is a list of 5 ToolDefinition objects; my_tool_registry now contains those tools
```

Demonstrates obtaining the factory from make_tools and using it with the default count to create and register tools.

#### Create and register a custom number of tools

```python
factory = make_tools(my_tool_registry)
created_tools = factory(3)
# created_tools is a list of 3 ToolDefinition objects; my_tool_registry has been updated with those 3 entries
```

Shows calling the returned function with an explicit count to create a specific number of tools.

### Complexity

Time: O(n) where n is the provided count (each iteration constructs an object and calls register). Space: O(n) additional space for the returned list of ToolDefinition objects.

### Related Functions

- `ToolRegistry.register` - make_tools calls this method to register each created ToolDefinition; behavior depends on ToolRegistry.register implementation
- `ToolDefinition.__init__` - make_tools constructs ToolDefinition instances using its constructor

### Notes

- The inner factory _make uses deterministic field values based on the loop index i (e.g., name 'tool-{i}', health_check_url 'https://example.com/tool-{i}/health').
- No explicit error handling is provided; any exceptions raised by ToolDefinition construction or tool_registry.register will propagate to the caller.
- Although the outer function make_tools itself does not perform registrations, the returned function _make performs registrations as a side effect.

---



#### _make

![Type: Sync](https://img.shields.io/badge/Type-Sync-green)

### Signature

```python
def _make(count: int = 5) -> list[ToolDefinition]
```

### Description

Create a list of ToolDefinition instances (default 5), register each one in the global tool_registry, and return the list.


The function allocates an empty list named tools, then iterates count times (0..count-1). On each iteration it constructs a ToolDefinition with deterministic fields: name 'tool-i', description 'Generated tool i', category 'generated', auth_required False, empty auth_scopes, a health_check_url using the index, health set to ToolHealth.HEALTHY, version '1.0.0', and tags ['generated']. It registers each created ToolDefinition by calling tool_registry.register(t), appends the instance to the local tools list, and after the loop returns the list of created ToolDefinition objects.

### Parameters

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `count` = `5` | `int` | ❌ | Number of ToolDefinition instances to create and register.
 |

### Returns

**Type:** `list[ToolDefinition]`

A list containing the ToolDefinition instances that were created and registered (length equals count).


**Possible Values:**

- A list with count ToolDefinition objects when count >= 0
- An empty list when count == 0

### Side Effects

> ❗ **IMPORTANT**
> This function has side effects that modify state or perform I/O operations.

- Calls tool_registry.register(t) for each created ToolDefinition, which mutates external/global registry state

### Usage Examples

#### Create and register three generated tools for use in tests

```python
_make(3)
```

Constructs three ToolDefinition instances, registers each with tool_registry, and returns the list of the three instances.

#### Use default count to create five generated tools

```python
_make()
```

Constructs and registers five ToolDefinition instances and returns them.

### Complexity

Time complexity O(n) where n == count due to one construction and one registration per item; space complexity O(n) for the returned list of ToolDefinition instances.

### Related Functions

- `tool_registry.register` - Called by _make to register each created ToolDefinition; external dependency

### Notes

- The function relies on the global tool_registry object and on ToolDefinition and ToolHealth types being available in scope.
- No validation is performed on the count parameter inside the function; negative values will result in no iterations because range(count) with negative count yields an empty sequence.
- Exceptions may propagate from ToolDefinition constructor or tool_registry.register, but the function itself contains no explicit raise statements.

---



#### make_events

![Type: Sync](https://img.shields.io/badge/Type-Sync-green)

### Signature

```python
def make_events() -> Callable[[int, EventTopic], list[Event]]
```

### Description

Factory fixture that returns a function which generates a list of Event instances.


make_events is a zero-argument factory function (commonly used as a pytest fixture) that defines and returns an inner function _make. The returned _make(count: int = 10, topic: EventTopic = EventTopic.SYSTEM) constructs and returns a list comprehension of Event objects. Each Event is created with source set to the literal "test-factory", topic set to the provided topic argument, action set to the string "action.{i}" where i is the event index, and payload set to a dict containing the index under the key 'index'. The factory itself does not perform any I/O or mutate external state; it only constructs and returns the inner function.

### Returns

**Type:** `Callable[[int, EventTopic], list[Event]]`

A function (_make) that when called produces a list of Event instances. _make accepts two parameters: count (number of events to generate) and topic (the EventTopic to assign to each Event).


**Possible Values:**

- A callable that when invoked returns a list of Event objects.
- When the returned callable is called with count=0, it returns an empty list.
- Default behavior when calling the returned callable with no arguments: returns 10 Event objects with topic EventTopic.SYSTEM.

### Usage Examples

#### Generate the default 10 system events in a test fixture

```python
events_maker = make_events()
events = events_maker()
```

Returns a list of 10 Event objects with topic EventTopic.SYSTEM, actions 'action.0' .. 'action.9' and payloads {'index': i}.

#### Generate 3 events with a custom topic

```python
events_maker = make_events()
custom_events = events_maker(count=3, topic=EventTopic.CUSTOM)
```

Returns a list of 3 Event objects, each using the provided EventTopic.CUSTOM and the corresponding action and payload values.

### Complexity

Time complexity: O(count) to construct the list of events. Space complexity: O(count) for the returned list and its Event objects.

### Related Functions

- `Event` - Type of objects created by the returned factory function; each item in the returned list is an Event instance.
- `EventTopic` - Type used for the topic parameter of the inner _make function; defaults to EventTopic.SYSTEM.

### Notes

- make_events itself takes no arguments and returns a factory function; tests typically call the returned function to generate events.
- The source field of every generated Event is the fixed string 'test-factory'.
- The action strings are deterministically derived from the index (f'action.{i}'), and payloads are simple dicts {'index': i}.
- No validation is performed on the count or topic parameters in the inner function; passing negative counts will result in an empty list from range(count).

---



#### _make

![Type: Sync](https://img.shields.io/badge/Type-Sync-green)

### Signature

```python
def _make(count: int = 10, topic: EventTopic = EventTopic.SYSTEM) -> list[Event]
```

### Description

Create and return a list of Event objects built from the provided count and topic.


This function constructs a list comprehension that produces 'count' Event instances. Each Event is created with a fixed source value 'test-factory', the provided topic, an action string formatted as 'action.{i}' where i is the zero-based index, and a payload dictionary containing the index under the key 'index'. The function returns the list of constructed Event objects.

### Parameters

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `count` = `10` | `int` | ❌ | Number of Event instances to create and include in the returned list.
<br>**Constraints:** Expected to be an integer (no runtime validation in function), If count is 0, an empty list is returned, Negative values follow Python range behavior (produces empty list for typical negative integers) |
| `topic` = `EventTopic.SYSTEM` | `EventTopic` | ❌ | Topic value to assign to every constructed Event.
<br>**Constraints:** Must be a value/instance acceptable to Event.topic (no validation in function) |

### Returns

**Type:** `list[Event]`

A list containing 'count' Event instances constructed with source 'test-factory', the provided topic, action strings 'action.0'..'action.{count-1}', and payloads {'index': i}.


**Possible Values:**

- List of length 'count' with Event objects
- Empty list if count is 0 or if range(count) yields no elements

### Usage Examples

#### Create three test events with the default topic

```python
_make(3)
```

Returns a list with Event(action='action.0', payload={'index': 0}), Event(action='action.1', payload={'index': 1}), and Event(action='action.2', payload={'index': 2}), all with source 'test-factory' and topic EventTopic.SYSTEM.

#### Create events with a custom topic

```python
_make(2, topic=EventTopic.CUSTOM)
```

Returns two Event instances with topic set to EventTopic.CUSTOM and actions 'action.0' and 'action.1'.

### Complexity

Time complexity O(n) where n is 'count' (each Event is constructed once). Space complexity O(n) for the returned list and the Event objects.

### Related Functions

- `Event` - Constructs instances of this class; the function calls Event(...) to create each element.
- `EventTopic` - Uses this enum/type for the default 'topic' parameter and to assign the topic of each Event.

### Notes

- The function assumes Event and EventTopic are available in scope and that Event can be instantiated with the shown keyword arguments.
- No input validation is performed; invalid types for 'count' or 'topic' will surface as normal Python errors from range() or Event constructor.
- Action strings are deterministic and based solely on the loop index.

---


