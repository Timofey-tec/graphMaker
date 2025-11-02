import sys
import os
import tomllib
import tarfile
import gzip
import urllib.request

CONFIG_PATH = "config.toml"

def load_config(path):
    if not os.path.exists(path):
        raise FileNotFoundError(f"Файл '{path}' не найден.")
    with open(path, "rb") as f:
        return tomllib.load(f)

def download_apk_index(repo_path, repo_mode):
    """Скачивает или открывает локальный APKINDEX"""
    index_path = "APKINDEX"
    if repo_mode == "remote":
        print(f"Загрузка APKINDEX из {repo_path} ...")
        urllib.request.urlretrieve(repo_path, "APKINDEX.tar.gz")
        with tarfile.open("APKINDEX.tar.gz", "r:gz") as tar:
            tar.extract("APKINDEX")
    else:
        local_file = os.path.join(repo_path, "APKINDEX")
        if not os.path.exists(local_file):
            raise FileNotFoundError(f"Не найден {local_file}")
        index_path = local_file
    return index_path

def parse_apk_index(index_path, package_name):
    """Парсит APKINDEX и возвращает прямые зависимости пакета"""
    deps = []
    current_pkg = None
    with open(index_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if line.startswith("P:"):
                current_pkg = line[2:]
            elif line.startswith("D:") and current_pkg == package_name:
                deps = [d for d in line[2:].split(" ") if d]
                break
    return deps

def main():
    try:
        config = load_config(CONFIG_PATH)
        package_name = config["package_name"]
        repo_path = config["repo_path"]
        repo_mode = config["repo_mode"]

        index_path = download_apk_index(repo_path, repo_mode)
        deps = parse_apk_index(index_path, package_name)

        if deps:
            print(f"Прямые зависимости для пакета '{package_name}':")
            for d in deps:
                print(f"  - {d}")
        else:
            print(f"Зависимости для пакета '{package_name}' не найдены.")

    except Exception as e:
        print(f"Ошибка: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
