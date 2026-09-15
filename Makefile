# Development commands. The runtime has no dependencies; these need uv and the Claude Code CLI.
PY := uv run --no-project --python 3.9 --with pytest python

.PHONY: test lint validate guard check

test:      ## pytest on Python 3.9, the floor the scripts must run on
	$(PY) -m pytest -q

lint:
	uvx ruff check scripts tests
	uvx ruff format --check scripts tests

validate:  ## plugin manifest and skill frontmatter
	claude plugin validate --strict .

guard:     ## nothing private tracked or untracked; no LinkedIn write tools or secrets in scripts/ or skills/
	@bad=$$(git ls-files --cached --others --exclude-standard | grep -E '(^|/)DESIGN\.md$$|^me/|\.sqlite'); \
	  if [ -n "$$bad" ]; then echo "private files present:"; echo "$$bad"; exit 1; fi
	@bad=$$(grep -rEn 'connect_with_person|send_message|search_people|get_sidebar_profiles|api_key|password' scripts skills); \
	  if [ -n "$$bad" ]; then echo "forbidden tokens:"; echo "$$bad"; exit 1; fi
	@echo "guard ok"

check: guard lint validate test
