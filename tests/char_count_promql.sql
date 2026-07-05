histogram_quantile(0.95, sum by (le, agent_name) (
  rate({"__name__"="workload.googleapis.com/agent.response.char_length", "monitored_resource"="generic_task"}[${__interval}])
))


sum(rate({"__name__"="workload.googleapis.com/agent.response.char_length_sum", "monitored_resource"="generic_task"}[${__interval}]))
/
sum(rate({"__name__"="workload.googleapis.com/agent.response.char_length_count", "monitored_resource"="generic_task"}[${__interval}]))


2. The Raw, Cumulative Total of All Characters

{"__name__"="workload.googleapis.com/agent.response.char_length_sum", "monitored_resource"="generic_task"}

 Total Characters Generated in the given window (e.g., per minute)

sum(increase({"__name__"="workload.googleapis.com/agent.response.char_length_sum", "monitored_resource"="generic_task"}[${__interval}]))
