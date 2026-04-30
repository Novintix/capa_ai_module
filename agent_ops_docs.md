Concepts
Core Concepts
Understanding the fundamental concepts of AgentOps

​
The AgentOps SDK Architecture
AgentOps is designed to provide comprehensive monitoring and analytics for AI agent workflows with minimal implementation effort. The SDK follows these key design principles:
​
Automated Instrumentation
After calling agentops.init(), the SDK automatically identifies installed LLM providers and instruments their API calls. This allows AgentOps to capture interactions between your code and the LLM providers to collect data for your dashboard without requiring manual instrumentation for every call.
​
Declarative Tracing with Decorators
The decorators system allows you to add tracing to your existing functions and classes with minimal code changes. Decorators create hierarchical spans that provide a structured view of your agent’s operations for monitoring and analysis.
​
OpenTelemetry Foundation
AgentOps is built on OpenTelemetry, a widely-adopted standard for observability instrumentation. This provides a robust and standardized approach to collecting, processing, and exporting telemetry data.
​
Sessions
A Session represents a single user interaction with your agent. When you initialize AgentOps using the init function, a session is automatically created for you:
import agentops

# Initialize AgentOps with automatic session creation
agentops.init(api_key="YOUR_API_KEY")
By default, all events and API calls will be associated with this session. For more advanced use cases, you can control session creation manually:
# Initialize without auto-starting a session
agentops.init(api_key="YOUR_API_KEY", auto_start_session=False)

# Later, manually start a session when needed
agentops.start_session(tags=["customer-query"])
​
Span Hierarchy
In AgentOps, activities are organized into a hierarchical structure of spans:
SESSION: The root container for all activities in a single execution of your workflow
AGENT: Represents an autonomous entity with specialized capabilities
WORKFLOW: A logical grouping of related operations
OPERATION/TASK: A specific task or function performed by an agent
LLM: An interaction with a language model
TOOL: The use of a tool or API by an agent
This hierarchy creates a complete trace of your agent’s execution:
SESSION
  ├── AGENT
  │     ├── OPERATION/TASK
  │     │     ├── LLM
  │     │     └── TOOL
  │     └── WORKFLOW
  │           └── OPERATION/TASK
  └── LLM (unattributed to a specific agent)
​
Agents
An Agent represents a component in your application that performs tasks. You can create and track agents using the @agent decorator:
from agentops.sdk.decorators import agent, operation

@agent(name="customer_service")
class CustomerServiceAgent:
    @operation
    def answer_query(self, query):
        # Agent logic here
        pass
​
LLM Events
AgentOps automatically tracks LLM API calls from supported providers, collecting valuable information like:
Model: The specific model used (e.g., “gpt-4”, “claude-3-opus”)
Provider: The LLM provider (e.g., “OpenAI”, “Anthropic”)
Prompt Tokens: Number of tokens in the input
Completion Tokens: Number of tokens in the output
Cost: The estimated cost of the interaction
Messages: The prompt and completion content
import agentops
from openai import OpenAI

# Initialize AgentOps
agentops.init(api_key="YOUR_API_KEY")

# Initialize the OpenAI client
client = OpenAI()

# This LLM call is automatically tracked
response = client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "What's the capital of France?"}]
)
​
Tags
Tags help you organize and filter your sessions. You can add tags when initializing AgentOps or when starting a session:
# Add tags when initializing
agentops.init(api_key="YOUR_API_KEY", tags=["production", "web-app"])

# Or when manually starting a session
agentops.start_session(tags=["customer-service", "tier-1"])
​
Host Environment
AgentOps automatically collects basic information about the environment where your agent is running:
Operating System: The OS type and version
Python Version: The version of Python being used
Hostname: The name of the host machine (anonymized)
SDK Version: The version of the AgentOps SDK being used
​
Dashboard Views
The AgentOps dashboard provides several ways to visualize and analyze your agent’s performance:
Session List: Overview of all sessions with filtering options
Timeline View: Chronological display of spans showing duration and relationships
Tree View: Hierarchical representation of spans showing parent-child relationships
Message View: Detailed view of LLM interactions with prompt and completion content
Analytics: Aggregated metrics across sessions and operations
​
Putting It All Together
A typical implementation looks like this:
import agentops
from openai import OpenAI
from agentops.sdk.decorators import agent, operation

# Initialize AgentOps
agentops.init(api_key="YOUR_API_KEY", tags=["production"])

# Define an agent
@agent(name="assistant")
class AssistantAgent:
    def __init__(self):
        self.client = OpenAI()
    
    @operation
    def answer_question(self, question):
        # This LLM call will be automatically tracked and associated with this agent
        response = self.client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": question}]
        )
        return response.choices[0].message.content

def workflow():
    # Use the agent
    assistant = AssistantAgent()
    answer = assistant.answer_question("What's the capital of France?")
    print(answer)

workflow()
# Session is automatically tracked until application terminates 



Concepts
Decorators
Use decorators to track activities in your agent system

​
Available Decorators
AgentOps provides the following decorators:
Decorator	Purpose	Creates
@session	Track an entire user interaction	SESSION span
@agent	Track agent classes and their lifecycle	AGENT span
@operation	Track discrete operations performed by agents	OPERATION span
@workflow	Track a sequence of operations	WORKFLOW span
@task	Track smaller units of work (similar to operations)	TASK span
@tool	Track tool usage and cost in agent operations	TOOL span
@guardrail	Track guardrail input and output	GUARDRAIL span
​
Decorator Hierarchy
The decorators create spans that form a hierarchy:
SESSION
  ├── AGENT
  │     ├── OPERATION or TASK
  │     │     ├── LLM
  │     │     └── TOOL
  │     └── WORKFLOW
  │           └── OPERATION or TASK
  └── AGENT
        └── OPERATION or TASK
​
Using Decorators
​
@session
The @session decorator tracks an entire user interaction from start to finish:
from agentops.sdk.decorators import session
import agentops

# Initialize AgentOps
agentops.init(api_key="YOUR_API_KEY")

@session
def answer_question(question):
    # Create and use agents
    weather_agent = WeatherAgent()
    result = weather_agent.get_forecast(question)
    
    # Return the final result
    return result
Each @session function call creates a new session span that contains all the agents, operations, and workflows used during that interaction.
​
@agent
The @agent decorator instruments a class to track its lifecycle and operations:
from agentops.sdk.decorators import agent, operation
import agentops

# Initialize AgentOps
agentops.init(api_key="YOUR_API_KEY")

@agent
class WeatherAgent:
    def __init__(self):
        self.api_key = "weather_api_key"
        
    @operation
    def get_forecast(self, location):
        # Get weather data
        return f"The weather in {location} is sunny."

def check_weather(city):
    weather_agent = WeatherAgent()
    forecast = weather_agent.get_forecast(city)
    return forecast

weather_info = check_weather("San Francisco")
When an agent-decorated class is instantiated within a session, an AGENT span is created automatically.
​
@operation
The @operation decorator tracks discrete functions performed by an agent:
from agentops.sdk.decorators import agent, operation
import agentops

# Initialize AgentOps
agentops.init(api_key="YOUR_API_KEY")

@agent
class MathAgent:
    @operation
    def add(self, a, b):
        return a + b
        
    @operation
    def multiply(self, a, b):
        return a * b

def calculate(x, y):
    math_agent = MathAgent()
    sum_result = math_agent.add(x, y)
    product_result = math_agent.multiply(x, y)
    return {"sum": sum_result, "product": product_result}

results = calculate(5, 3)
Operations represent the smallest meaningful units of work in your agent system. Each operation creates an OPERATION span with:
Inputs (function arguments)
Output (return value)
Duration
Success/failure status
​
@workflow
The @workflow decorator tracks a sequence of operations that work together:
from agentops.sdk.decorators import agent, operation, workflow
import agentops

# Initialize AgentOps
agentops.init(api_key="YOUR_API_KEY")

@agent
class TravelAgent:
    def __init__(self):
        self.flight_api = FlightAPI()
        self.hotel_api = HotelAPI()
    
    @workflow
    def plan_trip(self, destination, dates):
        # This workflow contains multiple operations
        flights = self.find_flights(destination, dates)
        hotels = self.find_hotels(destination, dates)
        
        return {
            "flights": flights,
            "hotels": hotels
        }
        
    @operation
    def find_flights(self, destination, dates):
        return self.flight_api.search(destination, dates)
        
    @operation
    def find_hotels(self, destination, dates):
        return self.hotel_api.search(destination, dates)
Workflows help you organize related operations and see their collective performance.
​
@task
The @task decorator is similar to @operation but can be used for smaller units of work:
from agentops.sdk.decorators import agent, task
import agentops

# Initialize AgentOps
agentops.init(api_key="YOUR_API_KEY")

@agent
class DataProcessor:
    @task
    def normalize_data(self, data):
        # Normalize the data
        return [x / sum(data) for x in data]
    
    @task
    def filter_outliers(self, data, threshold=3):
        # Filter outliers
        mean = sum(data) / len(data)
        std_dev = (sum((x - mean) ** 2 for x in data) / len(data)) ** 0.5
        
        return [x for x in data if abs(x - mean) <= threshold * std_dev]
The @task and @operation decorators function identically (they are aliases in the codebase), and you can choose the one that best fits your semantic needs.
​
@tool
The @tool decorator tracks tool usage within agent operations and supports cost tracking. It works with all function types: synchronous, asynchronous, generator, and async generator.
from agentops.sdk.decorators import agent, tool
import asyncio

@agent
class ProcessingAgent:
    def __init__(self):
        pass

    @tool(cost=0.01)
    def sync_tool(self, item):
        """Synchronous tool with cost tracking."""
        return f"Processed {item}"

    @tool(cost=0.02)
    async def async_tool(self, item):
        """Asynchronous tool with cost tracking."""
        await asyncio.sleep(0.1)
        return f"Async processed {item}"

    @tool(cost=0.03)
    def generator_tool(self, items):
        """Generator tool with cost tracking."""
        for item in items:
            yield self.sync_tool(item)

    @tool(cost=0.04)
    async def async_generator_tool(self, items):
        """Async generator tool with cost tracking."""
        for item in items:
            await asyncio.sleep(0.1)
            yield await self.async_tool(item)
The tool decorator provides:
Cost tracking for each tool call
Proper span creation and nesting
Support for all function types (sync, async, generator, async generator)
Cost accumulation in generator and async generator operations
​
@guardrail
The @guardrail decorator tracks guardrail input and output. You can specify the guardrail type ("input" or "output") with the spec parameter.
from agentops.sdk.decorators import guardrail
import agentops
import re

# Initialize AgentOps
agentops.init(api_key="YOUR_API_KEY")

@guardrail(spec="input")
def secret_key_guardrail(input):
    pattern = r'\bsk-[a-zA-Z0-9]{10,}\b'
    result = True if re.search(pattern, input) else False
    return {
        "tripwire_triggered" : result
    }
​
Decorator Attributes
You can pass additional attributes to decorators:
from agentops.sdk.decorators import agent, operation
import agentops

# Initialize AgentOps
agentops.init(api_key="YOUR_API_KEY")

@agent(name="custom_agent_name", attributes={"version": "1.0"})
class CustomAgent:
    @operation(name="custom_operation", attributes={"importance": "high"})
    def process(self, data):
        return data
Common attributes include:
Attribute	Description	Example
name	Custom name for the span	name="weather_forecast"
attributes	Dictionary of custom attributes	attributes={"model": "gpt-4"}
​
Complete Example
Here’s a complete example using all the decorators together:
from agentops.sdk.decorators import session, agent, operation, workflow, task
import agentops

# Initialize AgentOps
agentops.init(api_key="YOUR_API_KEY")

@session
def assist_user(query):
    # Create the main assistant
    assistant = Assistant()
    
    # Process the query
    return assistant.process_query(query)

@agent
class Assistant:
    def __init__(self):
        pass
    
    @workflow
    def process_query(self, query):
        research_agent = ResearchAgent()
        writing_agent = WritingAgent()
        
        # Research phase
        research = research_agent.gather_information(query)
        
        # Writing phase
        response = writing_agent.generate_response(query, research)
        
        return response

@agent
class ResearchAgent:
    @operation
    def gather_information(self, query):
        # Perform web search
        search_results = self.search(query)
        
        # Analyze results
        return self.analyze_results(search_results)
    
    @task
    def search(self, query):
        # Simulate web search
        return [f"Result for {query}", f"Another result for {query}"]
    
    @task
    def analyze_results(self, results):
        # Analyze search results
        return {"summary": "Analysis of " + ", ".join(results)}

@agent
class WritingAgent:
    @operation
    def generate_response(self, query, research):
        # Generate a response based on the research
        return f"Answer to '{query}' based on: {research['summary']}"

assist_user("What is the capital of France?")
In this example:
The @session decorator wraps the entire interaction
The @agent decorator defines multiple agent classes
The @workflow decorator creates a workflow that coordinates agents
The @operation and @task decorators track individual operations
All spans are properly nested in the hierarchy
Note that LLM and TOOL spans are automatically created when you use compatible LLM libraries or tool integrations.
​
Best Practices
Use @session for top-level functions that represent complete user interactions
Apply @agent to classes that represent distinct components of your system
Use @operation for significant functions that represent complete units of work
Use @task for smaller functions that are part of larger operations
Apply @workflow to methods that coordinate multiple operations
Keep decorator nesting consistent with the logical hierarchy of your code
Add custom attributes to provide additional context for analysis
Use meaningful names for all decorated components
​
Dashboard Visualization
In the AgentOps dashboard, decorators create spans that appear in:
Timeline View: Shows the execution sequence and duration
Hierarchy View: Displays the parent-child relationships
Detail Panels: Shows inputs, outputs, and attributes
Performance Metrics: Tracks execution times and success rates
This visualization helps you understand the flow and performance of your agent system. 


Concepts
Traces
Effectively manage traces in your agent workflow

​
Automatic Trace Management
The simplest way to create and manage traces is to use the init function with automatic trace creation:
import agentops

# Initialize with automatic trace creation (default)
agentops.init(api_key="YOUR_API_KEY", default_tags=["production"])
This approach:
Creates a trace automatically when you initialize the SDK
Tracks all events in the context of this trace
Manages the trace throughout the lifecycle of your application
​
Manual Trace Creation
For more control, you can disable automatic trace creation and start traces manually:
import agentops

# Initialize without auto-starting a trace
agentops.init(api_key="YOUR_API_KEY", auto_start_session=False)

# Later, manually start a trace when needed
trace_context = agentops.start_trace(
    trace_name="Customer Workflow", 
    tags=["customer-query", "high-priority"]
)

# End the trace when done
agentops.end_trace(trace_context, end_state="Success")
Manual trace management is useful when:
You want to control exactly when trace tracking begins
You need to associate different traces with different sets of tags
Your application has distinct workflows that should be tracked separately
​
Using the Trace Decorator
You can use the @trace decorator to create a trace for a specific function:
import agentops

@agentops.trace
def process_customer_data(customer_id):
    # This entire function execution will be tracked as a trace
    return analyze_data(customer_id)

# Or with custom parameters
@agentops.trace(name="data_processing", tags=["analytics"])
def analyze_user_behavior(user_data):
    return perform_analysis(user_data)
​
Trace Context Manager
TraceContext objects support Python’s context manager protocol, making it easy to manage trace lifecycles:
import agentops

# Using trace context as a context manager
with agentops.start_trace("user_session", tags=["web"]) as trace:
    # All operations here are tracked within this trace
    process_user_request()
    # Trace automatically ends when exiting the context
    # Success/Error state is set based on whether exceptions occurred
​
Trace States
Every trace has an associated state that indicates its completion status. AgentOps provides multiple ways to specify trace end states for flexibility and backward compatibility.
​
AgentOps TraceState Enum (Recommended)
The recommended approach is to use the TraceState enum from AgentOps:
from agentops import TraceState

# Available states
agentops.end_trace(trace_context, end_state=TraceState.SUCCESS)  # Trace completed successfully
agentops.end_trace(trace_context, end_state=TraceState.ERROR)    # Trace encountered an error
agentops.end_trace(trace_context, end_state=TraceState.UNSET)    # Trace state is not determined
​
OpenTelemetry StatusCode
For advanced users familiar with OpenTelemetry, you can use StatusCode directly:
from opentelemetry.trace.status import StatusCode

agentops.end_trace(trace_context, end_state=StatusCode.OK)     # Same as TraceState.SUCCESS
agentops.end_trace(trace_context, end_state=StatusCode.ERROR)  # Same as TraceState.ERROR
agentops.end_trace(trace_context, end_state=StatusCode.UNSET)  # Same as TraceState.UNSET
​
String Values
String values are also supported for convenience:
# String representations
agentops.end_trace(trace_context, end_state="Success")        # Maps to SUCCESS
agentops.end_trace(trace_context, end_state="Error")          # Maps to ERROR  
agentops.end_trace(trace_context, end_state="Indeterminate")  # Maps to UNSET
​
State Mapping
All state representations map to the same underlying OpenTelemetry StatusCode:
AgentOps TraceState	OpenTelemetry StatusCode	String Values	Description
TraceState.SUCCESS	StatusCode.OK	”Success”	Trace completed successfully
TraceState.ERROR	StatusCode.ERROR	”Error”	Trace encountered an error
TraceState.UNSET	StatusCode.UNSET	”Indeterminate”	Trace state is not determined
​
Default Behavior
If no end state is provided, the default is TraceState.SUCCESS:
# These are equivalent
agentops.end_trace(trace_context)
agentops.end_trace(trace_context, end_state=TraceState.SUCCESS)
​
Trace Attributes
Every trace collects comprehensive metadata to provide rich context for analysis. Trace attributes are automatically captured by AgentOps and fall into several categories:
​
Core Trace Attributes
Identity and Timing:
Trace ID: A unique identifier for the trace
Span ID: Identifier for the root span of the trace
Start Time: When the trace began
End Time: When the trace completed (set automatically)
Duration: Total execution time (calculated automatically)
User-Defined Attributes:
Trace Name: Custom name provided when starting the trace
Tags: Labels for filtering and grouping (list of strings or dictionary)
End State: Success, error, or unset status
# Tags can be provided as a list of strings or a dictionary
agentops.start_trace("my_trace", tags=["production", "experiment-a"])
agentops.start_trace("my_trace", tags={"environment": "prod", "version": "1.2.3"})
​
Resource Attributes
AgentOps automatically captures system and environment information:
Project and Service:
Project ID: AgentOps project identifier
Service Name: Service name (defaults to “agentops”)
Service Version: Version of your service
Environment: Deployment environment (dev, staging, prod)
SDK Version: AgentOps SDK version being used
Host System Information:
Host Name: Machine hostname
Host System: Operating system (Windows, macOS, Linux)
Host Version: OS version details
Host Processor: CPU architecture information
Host Machine: Machine type identifier
Performance Metrics:
CPU Count: Number of available CPU cores
CPU Percent: CPU utilization at trace start
Memory Total: Total system memory
Memory Available: Available system memory
Memory Used: Currently used memory
Memory Percent: Memory utilization percentage
Dependencies:
Imported Libraries: List of Python packages imported in your environment
​
Span Hierarchy
Nested Operations:
Spans: All spans (operations, agents, tools, workflows) recorded during the trace
Parent-Child Relationships: Hierarchical structure of operations
Span Kinds: Types of operations (agents, tools, workflows, tasks)
​
Accessing Trace Attributes
While most attributes are automatically captured, you can access trace information programmatically:
import agentops

# Start a trace and get the context
trace_context = agentops.start_trace("my_workflow", tags={"version": "1.0"})

# Access trace information
trace_id = trace_context.span.get_span_context().trace_id
span_id = trace_context.span.get_span_context().span_id

print(f"Trace ID: {trace_id}")
print(f"Span ID: {span_id}")

# End the trace
agentops.end_trace(trace_context)
​
Custom Attributes
You can add custom attributes to spans within your trace:
import agentops

with agentops.start_trace("custom_workflow") as trace:
    # Add custom attributes to the current span
    trace.span.set_attribute("custom.workflow.step", "data_processing")
    trace.span.set_attribute("custom.batch.size", 100)
    trace.span.set_attribute("custom.user.id", "user_123")
    
    # Your workflow logic here
    process_data()
​
Attribute Naming Conventions
AgentOps follows OpenTelemetry semantic conventions for attribute naming:
AgentOps Specific: agentops.* (e.g., agentops.span.kind)
GenAI Operations: gen_ai.* (e.g., gen_ai.request.model)
System Resources: Standard names (e.g., host.name, service.name)
Custom Attributes: Use your own namespace (e.g., myapp.user.id)
​
Trace Context
Traces create a context for all span recording. When a span is recorded:
It’s associated with the current active trace
It’s automatically included in the trace’s timeline
It inherits the trace’s tags for filtering and analysis
​
Viewing Traces in the Dashboard
The AgentOps dashboard provides several views for analyzing your traces:
Trace List: Overview of all traces with filtering options
Trace Details: In-depth view of a single trace
Timeline View: Chronological display of all spans in a trace
Tree View: Hierarchical representation of agents, operations, and events
Analytics: Aggregated metrics across traces
​
Best Practices
Start traces at logical boundaries in your application workflow
Use descriptive trace names to easily identify them in the dashboard
Apply consistent tags to group related traces
Use fewer, longer traces rather than many short ones for better analysis
Use automatic trace management unless you have specific needs for manual control
Leverage context managers for automatic trace lifecycle management
Set appropriate end states to track success/failure rates


Spans
Understanding the different types of spans in AgentOps

​
Core Span Types
AgentOps organizes all spans with specific kinds:
Span Kind	Description
SESSION	The root container for all activities in a single execution of your workflow
AGENT	Represents an autonomous entity with specialized capabilities
WORKFLOW	A logical grouping of related operations
OPERATION	A specific task or function performed by an agent
TASK	Alias for OPERATION, used interchangeably
LLM	An interaction with a language model
TOOL	The use of a tool or API by an agent
​
Span Hierarchy
Spans in AgentOps are organized hierarchically:
SESSION
  ├── AGENT
  │     ├── OPERATION/TASK
  │     │     ├── LLM
  │     │     └── TOOL
  │     └── WORKFLOW
  │           └── OPERATION/TASK
  └── LLM (unattributed to a specific agent)
Every span exists within the context of a session, and most spans (other than the session itself) have a parent span that provides context.
​
Span Attributes
All spans in AgentOps include:
ID: A unique identifier
Name: A descriptive name
Kind: The type of span (SESSION, AGENT, etc.)
Start Time: When the span began
End Time: When the span completed
Status: Success or error status
Attributes: Key-value pairs with additional metadata
Different span types have specialized attributes:
​
LLM Spans
LLM spans track interactions with large language models and include:
Model: The specific model used (e.g., “gpt-4”, “claude-3-opus”)
Provider: The LLM provider (e.g., “OpenAI”, “Anthropic”)
Prompt Tokens: Number of tokens in the input
Completion Tokens: Number of tokens in the output
Cost: The estimated cost of the interaction
Messages: The prompt and completion content
​
Tool Spans
Tool spans track the use of tools or APIs and include:
Tool Name: The name of the tool used
Input: The data provided to the tool
Output: The result returned by the tool
Duration: How long the tool operation took
​
Operation/Task Spans
Operation spans track specific functions or tasks:
Operation Type: The kind of operation performed
Parameters: Input parameters to the operation
Result: The output of the operation
Duration: How long the operation took
​
Creating Spans
There are several ways to create spans in AgentOps:
​
Using Decorators
The recommended way to create spans is using decorators:
from agentops.sdk.decorators import agent, operation, session, workflow, task

@session
def my_workflow():
    agent_instance = MyAgent()
    return agent_instance.perform_task()

@agent
class MyAgent:
    @operation
    def perform_task(self):
        # Perform the task
        return result
​
Automatic Instrumentation
AgentOps automatically instruments LLM API calls from supported providers when auto_instrument=True (the default):
import agentops
from openai import OpenAI

# Initialize AgentOps
agentops.init(api_key="YOUR_API_KEY")

# Initialize the OpenAI client
client = OpenAI()

# This LLM call will be automatically tracked
response = client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "Hello!"}]
)
​
Viewing Spans in the Dashboard
All recorded spans are visible in the AgentOps dashboard:
Timeline View: Shows the sequence and duration of spans
Tree View: Displays the hierarchical relationship between spans
Details Panel: Provides in-depth information about each span
Analytics: Aggregates statistics across spans
​
Best Practices
Use descriptive names for spans to make them easily identifiable
Create a logical hierarchy with sessions, agents, and operations
Record relevant parameters and results for better debugging
Use consistent naming conventions for span types
Track costs and token usage to monitor resource consumption 



Tags
Organize and filter your sessions with customizable tags

​
Adding Tags
You can add tags when initializing AgentOps, whicreh is the most common approach:
import agentops

# Initialize AgentOps with tags
agentops.init(
    api_key="YOUR_API_KEY",
    default_tags=["production", "customer-service", "gpt-4"]
)
Alternatively, when using manual trace creation:
# Initialize without auto-starting a session
agentops.init(api_key="YOUR_API_KEY", auto_start_session=False)

# Later start a trace with specific tags (modern approach)
trace = agentops.start_trace(trace_name="test_workflow", default_tags=["development", "testing", "claude-3"])
Legacy approach using agentops.start_session(default_tags=["development", "testing", "claude-3"]) is deprecated and will be removed in v4.0. Use agentops.start_trace() instead.
​
Tag Use Cases
Tags can be used for various purposes:
​
Environment Identification
Tag sessions based on their environment:
default_tags=["production"] # or ["development", "staging", "testing"]
​
Feature Tracking
Tag sessions related to specific features or components:
default_tags=["search-functionality", "user-authentication", "content-generation"]
​
User Segmentation
Tag sessions based on user characteristics:
default_tags=["premium-user", "new-user", "enterprise-customer"]
​
Experiment Tracking
Tag sessions as part of specific experiments:
default_tags=["experiment-123", "control-group", "variant-A"]
​
Model Identification
Tag sessions with the models being used:
default_tags=["gpt-4", "claude-3-opus", "mistral-large"]
​
Viewing Tagged Sessions
In the AgentOps dashboard:
Use the tag filter to select specific tags
Combine multiple tags to refine your view
Save filtered views for quick access
​
Best Practices
Use a consistent naming convention for tags
Include both broad categories and specific identifiers
Avoid using too many tags per session (3-5 is typically sufficient)
Consider using hierarchical tag structures (e.g., “env:production”, “model:gpt-4”)
Update your tagging strategy as your application evolves 



LangGraph
Track and analyze your LangGraph workflows with AgentOps

LangGraph is a framework for building stateful, multi-step applications with LLMs as graphs. AgentOps automatically instruments LangGraph to provide comprehensive observability into your graph-based agent workflows.
​
Core Concepts
LangGraph enables you to build complex agentic workflows as graphs with:
Nodes: Individual steps in your workflow (agents, tools, functions)
Edges: Connections between nodes that define flow
State: Shared data that flows through the graph
Conditional Edges: Dynamic routing based on state or outputs
Cycles: Support for iterative workflows and feedback loops
​
Installation
Install AgentOps and LangGraph along with LangChain dependencies:

pip

poetry

uv
pip install agentops langgraph langchain-openai python-dotenv
​
Setting Up API Keys
You’ll need API keys for AgentOps and your LLM provider:
OPENAI_API_KEY: From the OpenAI Platform
AGENTOPS_API_KEY: From your AgentOps Dashboard
Set these as environment variables or in a .env file.

Export to CLI

Set in .env file
OPENAI_API_KEY="your_openai_api_key_here"
AGENTOPS_API_KEY="your_agentops_api_key_here"
Then load them in your Python code:
from dotenv import load_dotenv
import os

load_dotenv()

AGENTOPS_API_KEY = os.getenv("AGENTOPS_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
​
Usage
Initialize AgentOps at the beginning of your application to automatically track all LangGraph operations:
import agentops
from typing import Annotated, Literal, TypedDict
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langchain_openai import ChatOpenAI

# Initialize AgentOps
agentops.init()

# Define your graph state
class AgentState(TypedDict):
    messages: Annotated[list, add_messages]

# Create your LLM
model = ChatOpenAI(temperature=0)

# Define nodes
def agent_node(state: AgentState):
    messages = state["messages"]
    response = model.invoke(messages)
    return {"messages": [response]}

# Build the graph
workflow = StateGraph(AgentState)
workflow.add_node("agent", agent_node)
workflow.set_entry_point("agent")
workflow.add_edge("agent", END)

# Compile and run
app = workflow.compile()
result = app.invoke({"messages": [{"role": "user", "content": "Hello!"}]})
​
What Gets Tracked
AgentOps automatically captures:
Graph Structure: Nodes, edges, and entry points during compilation
Execution Flow: The path taken through your graph
Node Executions: Each node execution with inputs and outputs
LLM Calls: All language model interactions within nodes
Tool Usage: Any tools called within your graph
State Changes: How state evolves through the workflow
Timing Information: Duration of each node and total execution time
​
Advanced Example
Here’s a more complex example with conditional routing and tools:
import agentops
from typing import Annotated, Literal, TypedDict
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool

# Initialize AgentOps
agentops.init()

# Define tools
@tool
def search(query: str) -> str:
    """Search for information."""
    return f"Search results for: {query}"

@tool
def calculate(expression: str) -> str:
    """Evaluate a mathematical expression."""
    try:
        return str(eval(expression))
    except:
        return "Error in calculation"

# Configure model with tools
tools = [search, calculate]
model = ChatOpenAI(temperature=0).bind_tools(tools)

# Define state
class AgentState(TypedDict):
    messages: Annotated[list, add_messages]

# Define conditional logic
def should_continue(state: AgentState) -> Literal["tools", "end"]:
    messages = state["messages"]
    last_message = messages[-1]
    
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"
    return "end"

# Define nodes
def call_model(state: AgentState):
    messages = state["messages"]
    response = model.invoke(messages)
    return {"messages": [response]}

def call_tools(state: AgentState):
    messages = state["messages"]
    last_message = messages[-1]
    
    tool_responses = []
    for tool_call in last_message.tool_calls:
        # Execute the appropriate tool
        if tool_call["name"] == "search":
            result = search.invoke(tool_call["args"])
        elif tool_call["name"] == "calculate":
            result = calculate.invoke(tool_call["args"])
        
        tool_responses.append({
            "role": "tool",
            "content": result,
            "tool_call_id": tool_call["id"]
        })
    
    return {"messages": tool_responses}

# Build the graph
workflow = StateGraph(AgentState)
workflow.add_node("agent", call_model)
workflow.add_node("tools", call_tools)
workflow.set_entry_point("agent")
workflow.add_conditional_edges(
    "agent",
    should_continue,
    {
        "tools": "tools",
        "end": END
    }
)
workflow.add_edge("tools", "agent")

# Compile and run
app = workflow.compile()
result = app.invoke({
    "messages": [{"role": "user", "content": "Search for AI news and calculate 25*4"}]
})
​
Dashboard Insights
In your AgentOps dashboard, you’ll see:
Graph Visualization: Visual representation of your compiled graph
Execution Trace: Step-by-step flow through nodes
Node Metrics: Performance data for each node
LLM Analytics: Token usage and costs across all model calls
Tool Usage: Which tools were called and their results
Error Tracking: Any failures in node execution
​
Examples
LangGraph Example
Complete example showing agent workflows with tools
​
Best Practices
Initialize Early: Call agentops.init() before creating your graph
Use Descriptive Names: Name your nodes clearly for better traces
Handle Errors: Implement error handling in your nodes
Monitor State Size: Large states can impact performance
Leverage Conditional Edges: Use them for dynamic workflows 


Langgraph
Build a basic chatbot with LangGraph and AgentOps tracking

View Notebook on Github
​
LangGraph Basic Chatbot with AgentOps
This example shows you how to build a basic chatbot using LangGraph’s StateGraph with comprehensive tracking via AgentOps.
​
What We’re Building
A stateful chatbot using LangGraph fundamentals:
🗃️ StateGraph: Core LangGraph structure for managing conversation state
💬 Chat Model: LLM integration for generating responses
🔄 State Management: Automatic message history tracking with add_messages
🎯 Graph Flow: START → chatbot node → END pattern
With AgentOps, you’ll get complete visibility into graph execution, state transitions, and LLM interactions.
​
Step-by-Step Implementation
​
Step 1: Install Dependencies
Install LangGraph with your preferred chat model and AgentOps for tracking:

pip

poetry

uv
pip install langgraph langchain agentops python-dotenv
What AgentOps adds:
📊 Graph execution tracking with node transitions and timing
💰 LLM cost monitoring with token usage breakdown
🔄 State change visualization showing message flow
📈 Performance metrics for each graph execution
🐛 Execution replay for debugging graph flows
​
Step 2: Create Your Project Structure
Create a simple Python project for your chatbot:
# Create project directory
mkdir langgraph_chatbot
cd langgraph_chatbot

# Create main chatbot file
touch chatbot.py
touch .env
This creates the basic structure:
langgraph_chatbot/
├── chatbot.py           # Main chatbot implementation
└── .env                 # API keys
​
Step 3: Set Up Environment Variables
Create your .env file with the necessary API keys:
# .env
OPENAI_API_KEY=your_openai_api_key_here
AGENTOPS_API_KEY=your_agentops_api_key_here
Get your API keys:
OpenAI API Key: OpenAI Platform
AgentOps API Key: AgentOps Settings
Note: You can use any LangChain-compatible model (Anthropic, Google, etc.) by adjusting the imports and model initialization.
​
Step 4: Build Your Basic Chatbot
Edit chatbot.py to create your LangGraph chatbot:
# chatbot.py
import os
from typing import Annotated
from typing_extensions import TypedDict

from langchain.chat_models import init_chat_model
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
import agentops
from dotenv import load_dotenv

# Load environment variables and initialize AgentOps
load_dotenv()
agentops.init(auto_start_session=False)

# Define the State schema
class State(TypedDict):
    # Messages have the type "list". The `add_messages` function
    # in the annotation defines how this state key should be updated
    # (in this case, it appends messages to the list, rather than overwriting them)
    messages: Annotated[list, add_messages]
​
Step 5: Initialize the Chat Model and Create the Chatbot Node
Add the model and node function:
# Initialize the chat model (you can change to any provider)
llm = init_chat_model("openai:gpt-4o-mini")

# Create the chatbot node function
def chatbot(state: State):
    """Main chatbot function that processes messages and returns responses."""
    return {"messages": [llm.invoke(state["messages"])]}
​
Step 6: Build and Compile the StateGraph
Construct your LangGraph workflow:
# Create the StateGraph
graph_builder = StateGraph(State)

# Add the chatbot node
# The first argument is the unique node name
# The second argument is the function that will be called
graph_builder.add_node("chatbot", chatbot)

# Add entry point (where to start)
graph_builder.add_edge(START, "chatbot")

# Add exit point (where to end)
graph_builder.add_edge("chatbot", END)

# Compile the graph
graph = graph_builder.compile()
​
Step 7: Add the Streaming Chat Function
Create the interactive chat interface with AgentOps tracking:
def stream_graph_updates(user_input: str):
    """Stream graph updates for the given user input."""
    for event in graph.stream({"messages": [{"role": "user", "content": user_input}]}):
        for value in event.values():
            print("Assistant:", value["messages"][-1].content)

def run_chatbot():
    """Main function to run the chatbot with AgentOps tracking."""
    # Start AgentOps session
    session = agentops.start_session(tags=["langgraph", "chatbot"])
    
    try:
        print("🤖 LangGraph Chatbot Started!")
        print("Type 'quit', 'exit', or 'q' to stop.\n")
        
        while True:
            try:
                user_input = input("User: ")
                if user_input.lower() in ["quit", "exit", "q"]:
                    print("Goodbye!")
                    break
                stream_graph_updates(user_input)
                print()  # Add blank line for readability
            except KeyboardInterrupt:
                print("\nGoodbye!")
                break
            except Exception as e:
                print(f"Error: {e}")
                break
        
        # End session successfully
        agentops.end_session("Success")
        
    except Exception as e:
        print(f"Error occurred: {e}")
        agentops.end_session("Failed", end_state_reason=str(e))
        raise

# Main execution
if __name__ == "__main__":
    run_chatbot()
​
Step 8: Run Your Chatbot
Execute your chatbot:
cd langgraph_chatbot
python chatbot.py
What happens:
AgentOps session starts automatically
Interactive chat loop begins
Each user message flows through: START → chatbot node → END
LLM generates responses based on conversation history
AgentOps captures all state transitions and LLM interactions
Session ends when you type ‘quit’
Example conversation:
🤖 LangGraph Chatbot Started!
Type 'quit', 'exit', or 'q' to stop.

User: Hello! What can you help me with?
Assistant: Hello! I'm a helpful AI assistant. I can help you with a wide variety of tasks...

User: Tell me a joke
Assistant: Why don't scientists trust atoms? Because they make up everything!

User: quit
Goodbye!
​
View Results in AgentOps Dashboard
After running your chatbot, visit your AgentOps Dashboard to see:
Graph Structure: Visual representation of your StateGraph (START → chatbot → END)
State Transitions: How messages flow through the graph
LLM Interactions: Every conversation turn with prompts and responses
Execution Timing: How long each node takes to process
Session Analytics: Conversation length, token usage, and costs
Message History: Complete conversation flow with state management
​
Key Files Created
Project structure you built:
chatbot.py - Complete LangGraph chatbot with AgentOps integration
.env - API keys for OpenAI and AgentOps
AgentOps Integration Points:
agentops.init() - Enables automatic LangGraph instrumentation
agentops.start_session() - Begins tracking each chat session
agentops.end_session() - Completes the session with status 


