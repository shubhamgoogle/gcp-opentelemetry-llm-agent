2. Absolute number of vowels in a given window

sum by (agent_name) (
  increase({"__name__"="workload.googleapis.com/agent.prompt.vowel_count", "monitored_resource"="generic_task"}[${__interval}])
)
