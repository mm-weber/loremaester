# `docker/user_tools/`

Bind-mounted into the R2R container at `/app/user_tools/` so R2R's
agent can load custom Python tool definitions at runtime.

## Status in this repo

**Not used.** This project puts its tool surface in Claude Code via MCP
servers (see `../../mcp-servers/` and `../../r2r_mcp_wrapper.py`), not
in R2R's agent runtime. Claude Code handles all reasoning — R2R is
restricted to embeddings, search, and ingestion, with no completion
provider configured.

The directory exists so R2R's container bind-mount stays valid even
when empty. `user_requirements.txt` here is the hook for extra Python
deps if you ever do register a tool.

## If you want to add R2R-side tools

You probably don't need to for this project's use case. If you're
extending R2R for a different workflow where the R2R agent itself
needs additional tools, follow R2R's upstream documentation at
https://r2r-docs.sciphi.ai/ — the interface (subclass
`core.base.agent.tools.base.Tool`, register in a config) lives
upstream and isn't mirrored here.

Register your tool in `../user_configs/<config>.toml` under the agent
section, add any Python deps to `user_requirements.txt`, and restart
the `r2r` service.
