# Policy semantics

The policy preserves explicit architectural decisions when imports change.
Upstream Tach checks actual imports against the graph; nox-tach checks additional
constraints on that graph. Policy violations should lead to a deliberate design
decision, not an automatic expansion of permissions.
See the [ownership map](ARCHITECTURE.md#ownership-map) for implementation and tests.

## Configuration and source roots

`nox_tach.toml` accepts only `[[modules]]` at the top level. Each policy `path`
must identify an exact module in `tach.toml`; consumer names belong in configuration.

Nox-tach requires explicit, nonempty `source_roots`, `exact = true`,
`root_module = "forbid"`, and a `depends_on` array on every Tach module.
Use `depends_on = []` when there are no dependencies. These are nox-tach's required
settings, not upstream Tach's permissive defaults.

Relative source roots resolve against the selected Tach file's parent;
`source_roots = ["."]` explicitly selects that directory.
Directory and single-file boundaries are supported. A directory boundary need not
contain `__init__.py`, but every top-level Python package that does contain it
needs its own exact declaration. Ambiguous resolution through multiple roots fails.
`--fix` never creates missing boundaries.

## Keys and patterns

| Module key | Meaning |
| --- | --- |
| `dependency_whitelist` | Permitted outgoing targets; the policy subtree is implicit |
| `dependency_blacklist` | Prohibited outgoing targets, including transitive paths |
| `parents_whitelist` | Permitted inbound callers; the policy subtree is implicit |
| `external_lib_whitelist` | Permitted external imports, in addition to stdlib and legal first-party imports |
| `dev_only` | Development-only status for the entire subtree |
| `test_root` | True-only marker for an aggregate test root |
| `test_mirror_component_suffix` | Required naming rule for a test root; may be empty |
| `test_infra` | True-only marker for reusable support below a test root |
| `collapse_references` | Canonicalize external consumers' references to this subtree |
| `collapse_references_except` | Keep matching consumers' outgoing references explicit when collapsing this subtree |

Patterns mean exact module (`pkg`), direct children (`pkg.*`), or recursive
descendants (`pkg.**`). Recursive descendants do not include the root.
Every pattern root must be an exact Tach module. A blacklist targeting a top-level
package must use the canonical pair `["pkg", "pkg.**"]`; nested roots use normal
pattern semantics.

## Inheritance and dependency direction

Omitting a whitelist introduces no new restriction at that boundary; it does not
reset inherited restrictions. An empty outgoing whitelist permits only that
policy's own subtree. Descendant outgoing and inbound whitelists may only narrow
their ancestors' permissions.

A child whitelist establishes a new implicit self-subtree. For example:

```toml
[[modules]]
path = "core"
dependency_whitelist = []

[[modules]]
path = "core.parser"
dependency_whitelist = []
```

With exact Tach declarations for these paths, `core.parser` can use itself and its
descendants, but cannot use `core.hashing` merely because both live under `core`.
Explicitly retaining `core.hashing` in the child's whitelist permits that sibling
only if the ancestor also permits it. Parent whitelists apply the same rule to
inbound callers. No module name receives a special exception.

Blacklists accumulate and cannot be reopened by child whitelists. If `A`
blacklists `C`, both `A -> C` and `A -> B -> C` violate policy.
The graph, rather than only direct import statements, determines this restriction.

A non-dev module cannot depend on an effectively dev-only module.
`dev_only = false` cannot override inherited or role-implied development status.
Declared values remain distinct from effective status in the typed models.

## External imports

External whitelists inspect Python import statements beneath the configured
boundary, including single-file boundaries. Stdlib and legal first-party imports
remain available; `external_lib_whitelist = []` prohibits third-party imports.
External permission does not bypass graph policy. Keep external libraries at the
smallest appropriate integration boundary and declare package dependencies
separately in the consumer's project metadata.

## Test roles

Test roots are disjoint, imply dev-only status, and require a mirror suffix:

```toml
[[modules]]
path = "specs"
test_root = true
test_mirror_component_suffix = "_spec"
```

Focused boundaries are progressive opt-in: declaring a test root does not require
every physical test directory to become an exact boundary. Each declared boundary
strictly below a root, except test infrastructure, mirrors a subject by removing
the suffix from each relative component. Thus `specs.core_spec.parser_spec`
mirrors `core.parser`. The subject must be an exact Tach module, and may itself
be dev-only. One root cannot contain duplicate identities for the same subject;
separate roots may mirror the same subject.

A focused test may depend on its subject subtree, that subtree's transitive
downstream dependencies, and declared test infrastructure. Upstream consumers do
not enter the cone. If `service -> core`, tests of `core` gain no permission to
import `service`. Aggregate boundaries need not fabricate direct subject imports.

The aggregate test root cannot be a dependency target. Modules outside a test root
cannot depend on its ordinary focused tests. Reusable support is declared explicitly:

```toml
[[modules]]
path = "specs.helpers"
test_infra = true
dependency_whitelist = []
external_lib_whitelist = ["pytest"]
```

Infrastructure must be strictly below a test root and explicitly declare both
whitelists, even when empty. It does not mirror a subject and cannot depend on
ordinary focused tests or aggregate roots. Other policy restrictions still apply.
Role markers accept only true; omit them instead of writing false.

## Normalization and Ruff

Dependencies are sorted/deduplicated. Tach modules group dependency-free production,
remaining production, then effective dev modules; policy blocks group production
before dev. Each group is alphabetical. Comments outside managed regions survive.

Collapsing is opt-in and affects consumers outside the selected subtree.
A reference to `core.parser` can become `core.**`; an exact `core` reference
remains separate. Internal dependencies stay explicit.
`collapse_references_except` exempts matching consumers and requires enabled
collapsing. For example:

```toml
[[modules]]
path = "core"
collapse_references = true
collapse_references_except = ["test.core_test.lib"]
```

Other external consumers' references to `core.lib` can collapse to `core.**`.
The outgoing references declared by `test.core_test.lib` stay explicit. Entries
identify consumers, rather than dependency targets; normal exact, `.*`, and `.**`
pattern semantics apply.

Starting with 0.2.0, rename `collapse_references_blacklist` to
`collapse_references_except` in TOML and in Python `ModulePolicy` construction or
attribute access. The values and collapse behavior stay the same. Both former keys,
`collapse_references_blacklist` and `collapse_references_exclude`, are rejected;
there are no compatibility aliases.

Ruff's `known-first-party` is generated from declared top-level Tach roots.
Manually maintained `known-third-party` entries take precedence.
The historical generated comment uses `America/New_York`; its timestamp changes
only when the list changes or its comment needs adding. Repeated fixes are
byte-identical. Other Ruff/Pyright policy belongs to the shared standards tooling.

## Repairing violations

| Failure | First action |
| --- | --- |
| Missing/ambiguous boundary or source root | Correct explicit topology before running fixes |
| Child widens inherited permissions | Check the parent's permissions and the child's new self-subtree |
| Transitive blacklist violation | Follow the reported dependency path and remove or redirect the offending edge |
| Test outside its subject cone | Move the test to its owning subject or use narrowly declared infrastructure |
| Invalid role or duplicate subject | Correct role placement or retain one canonical mirror identity |
| External import violation | Check whether that integration belongs at the boundary before adding permission |
| Configuration differs from canonical output | Run the [convergence commands](DEVELOPMENT.md#verification) and review the diff |

Use the [execution contract](ARCHITECTURE.md#execution-contract) to distinguish
failures before writes from policy failures after normalization.
