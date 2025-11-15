import sys
import os
import tomllib
import tarfile
import urllib.request
import ssl
from collections import deque, defaultdict
import subprocess

CONFIG_PATH = "config.toml"


def load_config(path):
    if not os.path.exists(path):
        raise FileNotFoundError(f"Файл '{path}' не найден.")
    with open(path, "rb") as f:
        return tomllib.load(f)


def validate_config(cfg):
    errors = []

    if not isinstance(cfg.get("package_name"), str) or not cfg["package_name"]:
        errors.append("Некорректное имя пакета.")

    if cfg.get("repo_mode") not in ("remote", "local", "test"):
        errors.append("repo_mode должен быть 'remote', 'local' или 'test'.")

    if not isinstance(cfg.get("repo_path"), str):
        errors.append("repo_path должен быть строкой.")

    if not isinstance(cfg.get("output_file"), str):
        errors.append("output_file должен быть строкой.")

    if not isinstance(cfg.get("ascii_mode"), bool):
        errors.append("ascii_mode должен быть true/false.")

    if not isinstance(cfg.get("max_depth"), int) or cfg["max_depth"] < 0:
        errors.append("max_depth должен быть целым числом ≥ 0.")

    if not isinstance(cfg.get("filter_substring"), str):
        errors.append("filter_substring должен быть строкой.")

    if errors:
        raise ValueError("\n".join(errors))



def download_apk_index(repo_path, repo_mode):
    """Загрузка APKINDEX с SSL-обходом для macOS/Windows"""
    if repo_mode == "remote":
        print(f"Загрузка APKINDEX из {repo_path} ...")
        ctx = ssl._create_unverified_context()

        with urllib.request.urlopen(repo_path, context=ctx) as response, open("APKINDEX.tar.gz", "wb") as out_file:
            out_file.write(response.read())

        with tarfile.open("APKINDEX.tar.gz", "r:gz") as tar:
            tar.extract("APKINDEX")
        return "APKINDEX"

    elif repo_mode == "local":
        local = os.path.join(repo_path, "APKINDEX")
        if not os.path.exists(local):
            raise FileNotFoundError(f"Не найден локальный файл: {local}")
        return local

    elif repo_mode == "test":
        return repo_path  # путь к тестовому файлу


def parse_apk_index(index_path, package_name, test_mode=False):
    """Чтение APKINDEX или тестового файла"""
    if test_mode:
        dep_map = {}
        with open(index_path, "r") as f:
            for line in f:
                if ":" not in line:
                    continue
                pkg, deps = line.strip().split(":")
                pkg = pkg.strip()
                deps = deps.strip().split() if deps.strip() else []
                dep_map[pkg] = deps
        return dep_map.get(package_name, [])

    deps = []
    current = None
    with open(index_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if line.startswith("P:"):
                current = line[2:]
            elif line.startswith("D:") and current == package_name:
                deps = [d for d in line[2:].split(" ") if d]
                break
    return deps



def get_all_dependencies_bfs(root_pkg, index_path, max_depth, filter_substring, test_mode):
    graph = defaultdict(list)
    visited = set()
    queue = deque([(root_pkg, 0)])

    while queue:
        pkg, depth = queue.popleft()

        if depth > max_depth:
            continue

        if pkg in visited:
            continue
        visited.add(pkg)

        if filter_substring and filter_substring in pkg:
            continue

        deps = parse_apk_index(index_path, pkg, test_mode=test_mode)
        graph[pkg] = deps

        if depth < max_depth:
            for d in deps:
                if d not in visited:
                    queue.append((d, depth + 1))

    return graph



def get_reverse_dependencies(graph):
    reverse_graph = defaultdict(list)
    for pkg, deps in graph.items():
        for d in deps:
            reverse_graph[d].append(pkg)
    return reverse_graph


def print_reverse_deps(reverse_graph, target):
    print(f"\nОбратные зависимости для '{target}':")
    if target not in reverse_graph or not reverse_graph[target]:
        print("  Нет пакетов, которые зависят от этого.")
        return
    for pkg in reverse_graph[target]:
        print(f"  - {pkg}")



def generate_dot(graph):
    lines = ["digraph G {"]
    for pkg, deps in graph.items():
        for dep in deps:
            lines.append(f'    "{pkg}" -> "{dep}";')
        if not deps:
            lines.append(f'    "{pkg}";')
    lines.append("}")
    return "\n".join(lines)


def save_graph_svg(dot_str, output_file):
    try:
        svg_file = output_file if output_file.endswith(".svg") else output_file + ".svg"
        process = subprocess.run(
            ["dot", "-Tsvg", "-o", svg_file],
            input=dot_str.encode("utf-8"),
            check=True
        )
        print(f"Граф сохранен в {svg_file}")
    except FileNotFoundError:
        print("Ошибка: Graphviz не установлен или не найден 'dot'")
    except subprocess.CalledProcessError as e:
        print("Ошибка при генерации SVG:", e)


def print_ascii_tree(graph, root, prefix=""):
    print(prefix + root)
    deps = graph.get(root, [])
    for i, dep in enumerate(deps):
        if i == len(deps) - 1:
            connector = "└─ "
            next_prefix = prefix + "   "
        else:
            connector = "├─ "
            next_prefix = prefix + "│  "
        print_ascii_tree(graph, dep, prefix=next_prefix + connector)



def main():
    try:
        config = load_config(CONFIG_PATH)
        validate_config(config)

        print("Загруженные параметры:")
        for key, value in config.items():
            print(f"{key} = {value}")
        print()

        test_mode = config["repo_mode"] == "test"

        print("Получение APKINDEX...")
        index_path = download_apk_index(config["repo_path"], config["repo_mode"])

        # Этап 2: прямые зависимости
        print(f"\nПрямые зависимости '{config['package_name']}':")
        direct = parse_apk_index(index_path, config["package_name"], test_mode)
        for d in direct:
            print(f"  - {d}")

        # Этап 3: граф BFS
        print("\nПостроение графа зависимостей (BFS)...")
        graph = get_all_dependencies_bfs(
            config["package_name"],
            index_path,
            config["max_depth"],
            config["filter_substring"],
            test_mode
        )

        print("\nГраф зависимостей (пакет → deps):")
        for pkg, deps in graph.items():
            print(f"{pkg}: {deps}")

        # Этап 4: обратные зависимости
        rev = get_reverse_dependencies(graph)
        print_reverse_deps(rev, config["package_name"])

        # Этап 5: визуализация
        dot_str = generate_dot(graph)
        save_graph_svg(dot_str, config["output_file"])

        if config["ascii_mode"]:
            print("\nASCII-дерево зависимостей:")
            print_ascii_tree(graph, config["package_name"])

    except Exception as e:
        print(f"Ошибка: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
