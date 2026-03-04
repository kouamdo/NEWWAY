# Development Bootstrap

This repository is an overlay for `ns-3-dev`. The main setup script (`sandbox_builder.sh`) is destructive in-place: it bootstraps a full `ns-3-dev` tree, removes top-level files (including `.git`), and deletes itself.

Use a disposable clone/workdir for setup.

## 1) Installation

Clone this repository:

```bash
git clone https://github.com/DriveX-devs/NEWWAY.git
cd NEWWAY
```

Run bootstrap:

```bash
printf '\n' | ./sandbox_builder.sh
```

First-time dependency install variant:

```bash
printf '\n' | ./sandbox_builder.sh install-dependencies
```

Alternative: use `scripts/bootstrap-disposable.sh` to run the same flow in a separate destination directory.

## 2) Configure

After bootstrap, switch to generated `ns-3-dev`:

```bash
cd ns-3-dev
./ns3 configure --build-profile=optimized --enable-examples --enable-tests --disable-python --disable-werror
```

## 3) Build

Minimal target build (recommended first check):

```bash
./ns3 build -j 2 v2v-simple-cam-exchange-80211p
```

Full build (can take a long time):

```bash
./ns3 build -j 2
```

## 4) Tests

`./ns3 test` is not a valid command in this tree. Use `test.py`:

```bash
./test.py --list
./test.py --no-build --suite=<suite-name>
```

## 5) Minimal Run Example

After the example is built:

```bash
./ns3 run --no-build "v2v-simple-cam-exchange-80211p"
```

## 6) Typical Problems

- `./ns3: No such file or directory`:
  - `ns3` exists only after `sandbox_builder.sh` creates `ns-3-dev`.
- `c++: fatal error: Killed signal terminated program cc1plus`:
  - Host hit OOM during compile. Reduce jobs (`-j 1` or `-j 2`) and/or add swap.
- Version mismatch risk:
  - README documents testing against SUMO `1.6.0` to `1.18.0`; newer SUMO versions can break integrations.
  - Ubuntu `24.04` is explicitly marked as not officially supported in README.
