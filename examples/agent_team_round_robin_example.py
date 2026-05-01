from agent_core import Agent, AgentTeam
from model_router import generate

planner = Agent(
    name="planner",
    model="ollama:gemma:e2b",
    execution_mode="direct",
    response_mode="pipeline",
    generate_fn=generate,
)

builder = Agent(
    name="builder",
    model="ollama:gemma:e2b",
    execution_mode="direct",
    response_mode="pipeline",
    generate_fn=generate,
)

reviewer = Agent(
    name="reviewer",
    model="ollama:gemma:e2b",
    execution_mode="direct",
    response_mode="pipeline",
    generate_fn=generate,
)

task = (
    "You are a team of three agents:\n"
    "- planner: proposes a clear plan\n"
    "- builder: implements the plan\n"
    "- reviewer: critiques and improves the result\n\n"
    "Work together to design a simple snake game in Python.\n"
    "Keep responses concise and build on previous messages.\n"
)

team = AgentTeam(
    agents=[planner, builder, reviewer],
    max_turns=10,
)

result = team.run(task)

print("FINAL RESULT:\n")
print(result.text)

print("\nTRANSCRIPT:\n")
for entry in result.transcript:
    print(f"{entry['agent']}: {entry['text']}\n")

print("\nEVENTS:\n")
for event in result.events:
    print(event["title"])
