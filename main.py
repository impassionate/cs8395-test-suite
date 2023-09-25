import argparse
import glob
import itertools
import os
import statistics
import subprocess
import json

from collections import defaultdict
from shutil import which, rmtree

# Check for vcstool
if which("vcs") is None:
    print("Run pip3 install . to install this package and its requirements!")
    exit(1)

# Parse arguments
parser = argparse.ArgumentParser(description="Run LLM test suites")
parser.add_argument("--repos", help=".repos file to import", required=True)
parser.add_argument("--model", help="Model to run all test suites against", required=False)
parser.add_argument("--config-view", help="Without running tests, get config breakdown of all repos", required=False, action="store_true")
parser.add_argument("--tags", help="Use repos that have one or more of these tags (space separated)", nargs="+", required=False)
args = parser.parse_args()

# Clone repos
rmtree("repos", ignore_errors=True)
os.mkdir("repos")
subprocess.Popen(f"vcs import --input {args.repos} repos", shell=True).wait()
print("----")

# Run tests for each repo
outputs = []
for file in itertools.chain(glob.glob("repos/*/config.json")):
    directory = os.path.dirname(file)
    data = json.loads(open(file).read())
    print(f"* {data['name']}")
    if args.model is not None:
        data["model"] = args.model

    if args.tags is not None:
        if len(set(args.tags).intersection(set(data["tags"]))) == 0:
            print("No tag match, skipped.")
            continue

    if args.config_view is True:
        print(f"Default Model: {data['model']}")
        print(f"Tags: {data['tags']}")
        continue

    # Run scripts
    if "run_test" in data:
        print("Running test script!")
        subprocess.Popen(f"{data['run_test']} --model {data['model']}", cwd=os.path.dirname(file), shell=True, stdout=subprocess.DEVNULL).wait()
    
    if "run_score" in data:
        print("Running scoring script!")
        subprocess.Popen(f"{data['run_score']} --model {data['model']}", cwd=os.path.dirname(file), shell=True, stdout=subprocess.DEVNULL).wait()

    # Get test output
    output = json.loads(open(os.path.join(directory, "output.json")).read())
    output["tags"] = data["tags"]
    output["name"] = data["name"]
    outputs.append(output)

# Coalesce output
if len(outputs) == 0:
    print("No test output!")
    exit()

score_by_tag = defaultdict(list)
scores = []
print("\n** Score by project")
for output in outputs:
    print(f"* {output['name']}")
    print(f"Overall score: {output['output']}")
    scores.append(output["output"])
    for tag in output["tags"]:
        score_by_tag[tag].append(output["output"])
    
    items = list(output.items())
    if len(items) > 3:
        for item in items:
            if item[0] == "output" or item[0] == "tags" or item[0] == "name":
                continue
            print(f"{item[0]}: {item[1]}")

print(f"\nAveraged score: {statistics.mean(scores)}")
print("\n** Score by tag")
for tag, scores in score_by_tag.items():
    print(f"* {tag}")
    print(f"Projects that match tag: {len(scores)}")
    print(f"Average score: {statistics.mean(scores)}")

output = {
    "overall": statistics.mean(scores),
    "by_tag": score_by_tag,
    "by_project": outputs
}

with open("output.json", "w") as f:
    f.write(json.dumps(output, indent=4))