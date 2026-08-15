import argparse
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
    parser.add_argument("prompt", type=str, help="Natural language description of the CFD simulation")
    parser.add_argument("-o", "--output", type=str, default="demo_run_cli", help="Output directory for the simulation case")
    
    args = parser.parse_args()
    
    # Run async main
    asyncio.run(run_simulation(args.prompt, args.output))

if __name__ == "__main__":
    main()
