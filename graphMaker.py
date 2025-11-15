import sys
import os
import tomllib
import tarfile
import urllib.request

CONFIG_PATH = "config.toml"


def load_config(path):
    if not os.path.exists(path):
        raise FileNotFoundError(f"Файл '{path}' не найден.")
    with open(path, "rb") as f:
        return tomllib.load(f)



def validate_config(cfg):
    errors = []

    #Имя пакета
    if not isinstance(cfg.get("package_name"), str) or not cfg["package_name"]:
        errors.append("Некорректное имя пакета.")

    #Режим репозитория
    if cfg.get("repo_mode") not in ("remote", "local"):
        errors.append("repo_mode должен быть 'remote' или 'local'.")

    #Путь или URL
    if not isinstance(cfg.get("repo_path"), str):
        errors.append("repo_path должен быть строкой.")

    #Имя выходного файла
    if not isinstance(cfg.get("output_file"), str):
        errors.append("output_file должен быть строкой.")

    #ASCII-режим
    if not isinstance(cfg.get("ascii_mode"), bool):
        errors.append("ascii_mode должен быть true/false.")

    #Максимальная глубина анализа
    if not isinstance(cfg.get("max_depth"), int) or cfg["max_depth"] < 0:
        errors.append("max_depth должен быть целым числом ≥ 0.")

    #Подстрока-фильтр
    if not isinstance(cfg.get("filter_substring"), str):
        errors.append("filter_substring должен быть строкой.")

    if errors:
        raise ValueError("\n".join(errors))



def download_apk_index(repo_path, repo_mode):
    if repo_mode == "remote":
        print(f"Загрузка APKINDEX из {repo_path} ...")
        urllib.request.urlretrieve(repo_path, "APKINDEX.tar.gz")
        with tarfile.open("APKINDEX.tar.gz", "r:gz") as tar:
            tar.extract("APKINDEX")
        return "APKINDEX"

    else:
        local = os.path.join(repo_path, "APKINDEX")
        if not os.path.exists(local):
            raise FileNotFoundError(f"Не найден локальный файл: {local}")
        return local



def parse_apk_index(index_path, package_name):
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


def main():
    try:
        config = load_config(CONFIG_PATH)
        validate_config(config)

        print("Загруженные параметры:")
        for key, value in config.items():
            print(f"{key} = {value}")
        print()

        print("Получение APKINDEX...")
        index_path = download_apk_index(config["repo_path"], config["repo_mode"])

        print(f"\nАнализ зависимостей пакета '{config['package_name']}'...")
        deps = parse_apk_index(index_path, config["package_name"])

        if deps:
            print("Прямые зависимости:")
            for d in deps:
                print(f"  - {d}")
        else:
            print("Зависимости не найдены.")

    except Exception as e:
        print(f"Ошибка: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
