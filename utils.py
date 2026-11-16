# Provide shared utility functions.

import hashlib
import csv
import gzip
import math
import shutil
import tempfile
from pathlib import Path


_NETWORKS_DIR = Path(__file__).resolve().parent / "data" / "networks"
_OUTPUT_DATA_DIR = Path(__file__).resolve().parent / "data" / "output_data"
_ENTITY_DATA_PATH = Path(__file__).resolve().parent / "data" / "entity_cob_new.csv"


def network_graph_path(filename: str) -> str:
    """Return the absolute path for a generated network GraphML file."""
    return str(_resolve_network_graph_path(filename))


def _resolve_network_graph_path(filename: str) -> Path:
    path = Path(filename)
    if path.is_absolute():
        return path
    if path.parts[:2] == ("data", "networks"):
        return _NETWORKS_DIR.joinpath(*path.parts[2:])
    return _NETWORKS_DIR / path


def read_network_graphml(filename: str):
    """Read a gzip-compressed GraphML network."""
    import networkx as nx

    with gzip.open(_resolve_network_graph_path(filename), "rb") as graph_file:
        return nx.read_graphml(graph_file)


def write_network_graphml(graph, filename: str) -> str:
    """Write a gzip-compressed GraphML network and return its path."""
    import networkx as nx

    output_path = _resolve_network_graph_path(filename)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(output_path, "wb") as graph_file:
        nx.write_graphml(graph, graph_file)
    return str(output_path)


def read_network_graphml_with_igraph(filename: str):
    """Read a gzip-compressed GraphML network with igraph."""
    import igraph as ig

    with tempfile.TemporaryDirectory() as temp_dir:
        uncompressed_path = Path(temp_dir) / "network.graphml"
        with gzip.open(_resolve_network_graph_path(filename), "rb") as graph_file:
            with uncompressed_path.open("wb") as output_file:
                shutil.copyfileobj(graph_file, output_file)
        return ig.Graph.Read_GraphML(str(uncompressed_path))


def output_data_path(*parts: str) -> str:
    """Return the absolute path for generated entity-linking output."""
    return str(_OUTPUT_DATA_DIR.joinpath(*parts))


def print_low_hdi_low_passport_percentages(graph) -> None:
    """Print valid-writer percentages by gender/transnational group."""
    entity_metrics = {}
    with _ENTITY_DATA_PATH.open(newline="", encoding="utf-8") as csv_file:
        for row in csv.DictReader(csv_file):
            try:
                metrics = (
                    float(row["HDI_value"]),
                    float(row["passport_mobility_score"]),
                )
            except (TypeError, ValueError):
                metrics = None
            if metrics is not None and all(math.isfinite(value) for value in metrics):
                entity_metrics[row["entity"]] = metrics
            else:
                entity_metrics[row["entity"]] = None

    groups = {
        (gender, transnational): {"total": 0, "valid": []}
        for gender in ("female", "male")
        for transnational in ("1", "0")
    }

    for node, attributes in graph.nodes(data=True):
        if attributes.get("writer") != "1":
            continue
        key = (attributes.get("gender"), attributes.get("transnational"))
        if key not in groups:
            continue
        group = groups[key]
        group["total"] += 1
        metrics = entity_metrics.get(node)
        if metrics is not None:
            group["valid"].append(metrics)

    valid_metrics = [
        metrics
        for group in groups.values()
        for metrics in group["valid"]
    ]
    if not valid_metrics:
        raise ValueError(
            "No writer nodes with valid HDI and passport metrics were found."
        )

    mean_passport = sum(passport for _, passport in valid_metrics) / len(valid_metrics)
    print(
        "\nNodi con HDI_value < 0.8 e passport_mobility_score sotto la media "
        f"della rete (media: {mean_passport:.2f}):"
    )
    for (gender, transnational), group in groups.items():
        valid = group["valid"]
        qualifying = sum(
            hdi < 0.8 and passport < mean_passport
            for hdi, passport in valid
        )
        if valid:
            percentage = qualifying / len(valid) * 100
            result = f"{qualifying}/{len(valid)} ({percentage:.2f}%)"
        else:
            result = "N/D (0 nodi con dati validi)"
        missing = group["total"] - len(valid)
        print(
            f" - gender={gender}, transnational={transnational}: {result}; "
            f"esclusi per dati mancanti/non numerici: {missing}"
        )


def string_to_hash(input_string: str, hash_type: str = "sha256") -> str:
    """
    Converts a string into a hash using the specified hashing algorithm.

    :param input_string: String to convert into a hash.
    :param hash_type: Hashing algorithm ('md5', 'sha1', 'sha256', 'sha512', etc.).
    :return: Hash string.
    """
    # Convert the string to bytes
    encoded_string = input_string.encode('utf-8')

    # Create the hash using the specified algorithm
    hash_function = getattr(hashlib, hash_type)
    hash_object = hash_function(encoded_string)

    # Return the hash in hexadecimal format
    return hash_object.hexdigest()
