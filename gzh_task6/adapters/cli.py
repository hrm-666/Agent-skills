"""
命令行适配器
"""
import logging
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown

from core.llm import LLM
from core.skills import SkillLoader
from core.tools import ToolRegistry
from core.agent import Agent

console = Console()


def run_cli(llm: LLM, skill_loader: SkillLoader, max_iterations: int):
    """交互式 CLI 模式"""
    tool_registry = ToolRegistry()
    agent = Agent(llm, skill_loader, tool_registry, max_iterations)
    
    console.print(Panel.fit(
        "[bold cyan]Mini Agent[/bold cyan] - 输入问题，输入 [yellow]exit[/yellow] 退出",
        border_style="cyan"
    ))
    console.print(f"[dim]已加载 {len(skill_loader.catalog)} 个 Skills | 最大迭代 {max_iterations} 轮[/dim]\n")
    
    while True:
        try:
            user_input = console.input("[bold green]You:[/bold green] ").strip()
            if user_input.lower() in ['exit', 'quit']:
                console.print("[yellow]Bye![/yellow]")
                break
            if not user_input:
                continue
            
            console.print("\n[bold blue]Agent:[/bold blue]")
            
            # 定义回调，实时显示步骤
            def on_step(step):
                if step["type"] == "tool_call":
                    console.print(f"  [dim]{step['name']}({step['args']})[/dim]")
                elif step["type"] == "tool_result":
                    result_preview = step["result"][:200] + "..." if len(step["result"]) > 200 else step["result"]
                    console.print(f"  [dim green]{result_preview}[/dim green]")
            
            answer = agent.run(user_input, on_step=on_step)
            console.print(Markdown(answer))
            console.print()
            
        except KeyboardInterrupt:
            console.print("\n[yellow]Interrupted, exiting...[/yellow]")
            break
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            logging.exception("CLI error")


def run_once(llm: LLM, skill_loader: SkillLoader, max_iterations: int, user_input: str):
    """单次执行模式"""
    tool_registry = ToolRegistry()
    agent = Agent(llm, skill_loader, tool_registry, max_iterations)
    
    console.print(f"[bold green]User:[/bold green] {user_input}\n")
    console.print("[bold blue]Agent:[/bold blue]")
    
    answer = agent.run(user_input, on_step=lambda step: None)  # 不显示中间步骤
    console.print(Markdown(answer))