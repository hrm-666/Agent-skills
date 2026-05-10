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
from core.memory import set_memory_mode, get_memory, clear_memory, reset_memory

console = Console()


def _print_skills(skill_loader: SkillLoader):
    """打印所有已加载的技能"""
    if not skill_loader.catalog:
        console.print("[yellow]未加载任何技能[/yellow]")
        return
    
    console.print(f"\n[bold cyan]📦 已加载 {len(skill_loader.catalog)} 个技能:[/bold cyan]\n")
    for name, meta in skill_loader.catalog.items():
        desc = meta.description[:80] + "..." if len(meta.description) > 80 else meta.description
        console.print(f"   • [green]{name}[/green] - {desc}")
    console.print()


def configure_memory():
    """配置记忆功能（每次启动时询问）"""
    console.print(Panel.fit(
        "[bold cyan]🧠 记忆功能配置[/bold cyan]",
        border_style="cyan"
    ))
    console.print("\n记忆模式说明：")
    console.print("  [yellow]1. 无记忆[/yellow] - 每次对话独立，不记住之前的内容")
    console.print("  [yellow]2. 有限记忆[/yellow] - 记住最近 N 轮对话")
    console.print("  [yellow]3. 永久记忆[/yellow] - 记住所有对话，保存到文件\n")
    
    console.print("[dim]请选择记忆模式 (1/2/3): [/dim]", end="")
    choice = input().strip()
    
    while choice not in ["1", "2", "3"]:
        console.print("[red]无效选择，请输入 1、2 或 3[/red]")
        console.print("[dim]请选择记忆模式 (1/2/3): [/dim]", end="")
        choice = input().strip()
    
    if choice == "1":
        set_memory_mode("none")
        console.print("[green]✓ 已设置为「无记忆」模式，每次对话独立[/green]")
    
    elif choice == "2":
        console.print("[dim]请输入保留的对话轮数 (默认 10): [/dim]", end="")
        limit_input = input().strip()
        try:
            limit = int(limit_input) if limit_input else 10
            if limit < 1:
                limit = 10
        except ValueError:
            limit = 10
        set_memory_mode("limited", limit)
        console.print(f"[green]✓ 已设置为「有限记忆」模式，保留最近 {limit} 轮对话[/green]")
    
    elif choice == "3":
        set_memory_mode("permanent")
        console.print("[green]✓ 已设置为「永久记忆」模式，所有对话将保存到文件[/green]")
    
    console.print()


def show_memory_status():
    """显示当前记忆状态"""
    memory = get_memory()
    info = memory.get_info()
    
    mode_names = {
        "none": "无记忆",
        "limited": f"有限记忆 (最近 {info['limit']} 轮)",
        "permanent": "永久记忆"
    }
    
    console.print(f"\n[dim]🧠 当前记忆模式: {mode_names.get(info['mode'], info['mode'])} | 已记忆 {info['count']} 轮对话[/dim]")


def clear_memory_confirmation():
    """清空记忆确认"""
    console.print("[dim]是否清空所有记忆？(y/N): [/dim]", end="")
    confirm = input().strip().lower()
    if confirm == 'y' or confirm == 'yes':
        clear_memory()
        console.print("[yellow]✓ 记忆已清空[/yellow]")


def run_cli(llm: LLM, skill_loader: SkillLoader, max_iterations: int):
    """交互式 CLI 模式"""
    # 每次启动都询问记忆配置
    reset_memory()  # 重置之前的记忆
    configure_memory()  # 重新询问配置
    
    tool_registry = ToolRegistry()
    agent = Agent(llm, skill_loader, tool_registry, max_iterations)
    
    console.print(Panel.fit(
        "[bold cyan]Mini Agent[/bold cyan] - 输入问题，输入 [yellow]exit[/yellow] 退出",
        border_style="cyan"
    ))
    
    _print_skills(skill_loader)
    show_memory_status()
    console.print(f"[dim]最大迭代 {max_iterations} 轮 | 输入 'skills' 显示技能 | 'memory' 查看记忆 | 'clear' 清空记忆[/dim]\n")
    
    while True:
        try:
            user_input = console.input("[bold green]You:[/bold green] ").strip()
            
            if user_input.lower() in ['exit', 'quit']:
                console.print("[yellow]Bye![/yellow]")
                break
            if not user_input:
                continue
            
            if user_input.lower() == 'skills':
                _print_skills(skill_loader)
                continue
            
            if user_input.lower() == 'memory':
                info = get_memory().get_info()
                
                content = f"模式: {info['mode']}\n"
                content += f"保留轮数: {info['limit'] or 'N/A'}\n"
                content += f"已记忆: {info['count']} 轮\n"
                
                if info['history'] and len(info['history']) > 0:
                    content += f"\n[bold]📝 最近记忆内容:[/bold]\n"
                    for i, exchange in enumerate(info['history'][-5:], 1):
                        content += f"\n  [dim]{i}. 用户:[/dim] {exchange['user'][:80]}"
                        if len(exchange['user']) > 80:
                            content += "..."
                        content += f"\n     [dim]助手:[/dim] {exchange['assistant'][:80]}"
                        if len(exchange['assistant']) > 80:
                            content += "..."
                        content += f"\n     [dim]时间: {exchange['timestamp'][:19]}[/dim]"
                else:
                    content += "\n[dim]暂无记忆内容[/dim]"
                
                console.print(Panel(
                    content,
                    title="🧠 记忆状态",
                    border_style="cyan"
                ))
                continue
            
            if user_input.lower() == 'clear':
                clear_memory_confirmation()
                continue
            
            console.print("\n[bold blue]Agent:[/bold blue]")
            
            def on_step(step):
                if step["type"] == "tool_call":
                    console.print(f"  [dim]🔧 {step['name']}({step['args']})[/dim]")
                elif step["type"] == "tool_result":
                    preview = step["result"][:150] + "..." if len(step["result"]) > 150 else step["result"]
                    console.print(f"  [dim green]✅ {preview}[/dim green]")
            
            answer = agent.run(user_input, on_step=on_step)
            console.print(Markdown(answer))
            console.print()
            
        except KeyboardInterrupt:
            console.print("\n[yellow]Bye![/yellow]")
            break
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            logging.exception("CLI error")


def run_once(llm: LLM, skill_loader: SkillLoader, max_iterations: int, user_input: str):
    """单次执行模式（不询问记忆配置）"""
    tool_registry = ToolRegistry()
    agent = Agent(llm, skill_loader, tool_registry, max_iterations)
    
    console.print(f"[bold green]User:[/bold green] {user_input}\n")
    console.print("[bold blue]Agent:[/bold blue]")
    
    answer = agent.run(user_input, on_step=lambda step: None)
    console.print(Markdown(answer))