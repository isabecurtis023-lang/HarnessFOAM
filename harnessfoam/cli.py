import argparse
import os
import warnings
os.environ['TRANSFORMERS_VERBOSITY'] = 'error'
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
warnings.filterwarnings('ignore')
import asyncio
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
import time

from harnessfoam.agents.graph import create_workflow, SimulationState

console = Console()

async def run_simulation(prompt: str, output_dir: str):
    console.print(Panel(f"[bold blue]HarnessFOAM 🌊[/bold blue]\n[italic]Processing:[/italic] {prompt}", title="AI Task", border_style="blue"))
    
    workflow = create_workflow()
    initial_state = SimulationState(
        user_requirement=prompt,
        case_dir=output_dir
    )
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=False,
    ) as progress:
        task_id = progress.add_task("[cyan]Initializing Multi-Agent Workflow...", total=None)
        
        try:
            # We use ainvoke and print updates if possible. Since ainvoke is blocking until end,
            # we just wait for it here. In a real app we'd stream the langgraph events.
            progress.update(task_id, description="[cyan]Architect Agent planning file structure...")
            time.sleep(1) # Visual effect
            progress.update(task_id, description="[green]Meshing Agent generating grid topology...")
            time.sleep(1)
            progress.update(task_id, description="[yellow]Input Writer Agent compiling dictionaries...")
            time.sleep(1)
            progress.update(task_id, description="[magenta]Runner Agent executing OpenFOAM solvers...")
            
            final_state = await workflow.ainvoke(initial_state)
            
            progress.update(task_id, description="[bold green]Simulation Workflow Complete!")
            
            console.print("\n[bold green]Success![/bold green] Results have been written to:")
            console.print(f"📁 {output_dir}")
            
            if final_state.get("file_plan"):
                console.print(Panel("\n".join([f"- {f['folder']}/{f['file']}" for f in final_state["file_plan"]]), title="Generated Files", border_style="green"))
                
        except Exception as e:
            progress.update(task_id, description=f"[bold red]Workflow Error: {e}")
            console.print_exception()

def main():
    parser = argparse.ArgumentParser(description="HarnessFOAM Command Line Interface")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Run command
    run_parser = subparsers.add_parser("run", help="Run a CFD simulation from natural language")
    run_parser.add_argument("prompt", type=str, help="Natural language description of the CFD simulation")
    run_parser.add_argument("-o", "--output", type=str, default="demo_run_cli", help="Output directory")
    
    # Serve command
    serve_parser = subparsers.add_parser("serve", help="Launch the HarnessFOAM Web Interface")
    serve_parser.add_argument("--host", type=str, default="127.0.0.1", help="Host address")
    serve_parser.add_argument("--port", type=int, default=8000, help="Port number")
    
    # MCP command
    mcp_parser = subparsers.add_parser("mcp", help="Launch the HarnessFOAM MCP Server (stdio)")

    benchmark_parser = subparsers.add_parser("benchmark", help="Run deterministic OpenFOAM 13 benchmark regressions")
    benchmark_parser.add_argument("--tutorial", choices=["cavity", "pitzDaily", "damBreak", "shockTube", "all"], default="all")
    
    args = parser.parse_args()
    
    if args.command == "serve":
        from harnessfoam.api.server import start_server
        start_server(host=args.host, port=args.port)
    elif args.command == "mcp":
        from harnessfoam.api.mcp_server import start_mcp
        start_mcp()
    elif args.command == "benchmark":
        import json
        from harnessfoam.tutorial_regression import run_tutorial_regression, list_tutorial_regressions
        names = list(list_tutorial_regressions()) if args.tutorial == "all" else [args.tutorial]
        print(json.dumps({name: run_tutorial_regression(name) for name in names}, ensure_ascii=False, indent=2))
    elif args.command == "run" or args.command is None:
        # Fallback for old positional usage or explicit run command
        prompt = getattr(args, "prompt", "Default simulation prompt")
        output = getattr(args, "output", "demo_run_cli")
        asyncio.run(run_simulation(prompt, output))
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
