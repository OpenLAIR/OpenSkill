import os
import shutil
from collections import defaultdict

CATEGORY_FOLDERS = {
    "LLM": "LLM",
    "trapped_ion_and_qc": "trapped_ion_and_qc",
    "black_hole": "black_hole",
    "DNA": "DNA",
    "music_history": "music_history",
}

def get_category_keywords():
    return {
        "LLM": {
            "large language model": 5.0, "llm": 5.0, "llms": 5.0,
            "transformer": 3.5, "transformers": 3.5,
            "gpt": 4.5, "gpt-4": 5.0, "gpt-3": 5.0, "chatgpt": 5.0,
            "bert": 4.0, "language model": 4.0, "language models": 4.0,
            "neural network": 2.0, "deep learning": 2.5,
            "natural language processing": 3.5, "nlp": 3.0,
            "attention mechanism": 3.5, "self-attention": 3.5,
            "fine-tuning": 3.0, "fine tuning": 3.0, "finetuning": 3.0,
            "prompt": 3.0, "prompting": 3.5, "in-context learning": 4.0,
            "reinforcement learning from human feedback": 5.0, "rlhf": 5.0,
            "token": 2.0, "tokenization": 3.0, "embedding": 2.5,
            "pretraining": 3.0, "pre-training": 3.0, "pretrained": 3.0,
            "text generation": 3.5, "machine translation": 3.0,
            "retrieval augmented": 4.0, "rag": 3.5,
            "instruction tuning": 4.0, "alignment": 2.5,
            "hallucination": 3.5, "benchmark": 2.0,
            "chain of thought": 4.0, "reasoning": 2.0,
            "diffusion model": 3.0, "generative ai": 4.0,
            "openai": 4.0, "anthropic": 4.0, "llama": 4.0,
            "mistral": 3.5, "gemini": 3.0,
        },
        "trapped_ion_and_qc": {
            "trapped ion": 6.0, "trapped ions": 6.0, "ion trap": 6.0,
            "qubit": 4.5, "qubits": 4.5,
            "quantum computing": 4.5, "quantum computer": 4.5,
            "quantum gate": 4.5, "quantum circuit": 4.0,
            "quantum entanglement": 4.0, "entanglement": 3.0,
            "quantum state": 3.5, "superposition": 3.5,
            "quantum error correction": 5.0, "quantum error": 4.0,
            "quantum algorithm": 4.0, "quantum simulation": 4.0,
            "quantum information": 3.5, "quantum memory": 4.0,
            "quantum network": 3.5, "quantum teleportation": 4.0,
            "quantum supremacy": 4.5, "quantum advantage": 4.0,
            "decoherence": 4.0, "coherence time": 4.0,
            "paul trap": 5.0, "penning trap": 5.0,
            "motional mode": 5.0, "phonon": 3.5,
            "molmer-sorensen": 5.0, "ms gate": 5.0,
            "quantum charge coupled device": 5.0,
            "sympathetic cooling": 5.0, "laser cooling": 4.0,
            "quantum logic": 4.0, "fault tolerant": 3.5,
            "surface code": 4.0, "stabilizer": 3.0,
            "quantum processor": 4.0, "quantum register": 4.0,
        },
        "black_hole": {
            "black hole": 5.0, "black holes": 5.0,
            "event horizon": 5.0, "schwarzschild": 5.0,
            "kerr black hole": 5.0, "kerr metric": 5.0,
            "gravitational wave": 4.5, "gravitational waves": 4.5,
            "general relativity": 3.5, "spacetime": 3.5,
            "singularity": 4.0, "accretion disk": 5.0, "accretion": 3.5,
            "hawking radiation": 5.0, "hawking": 3.0,
            "neutron star": 3.5, "pulsar": 3.5,
            "galaxy": 2.5, "quasar": 4.0, "active galactic": 4.0,
            "dark matter": 3.5, "dark energy": 3.0,
            "gravitational lensing": 4.0, "redshift": 3.0,
            "cosmic": 2.5, "astrophysic": 3.5,
            "supermassive": 4.5, "stellar mass": 3.5,
            "binary merger": 4.0, "ligo": 4.5, "virgo": 3.5,
            "penrose": 3.5, "ergosphere": 5.0,
            "photon sphere": 5.0, "innermost stable": 5.0,
            "no-hair theorem": 5.0, "information paradox": 5.0,
            "bekenstein": 5.0, "ads/cft": 4.0,
        },
        "DNA": {
            "dna": 4.0, "dna sequence": 5.0, "dna replication": 5.0,
            "genome": 4.5, "genomic": 4.0, "genomics": 4.0,
            "crispr": 5.0, "cas9": 5.0, "gene editing": 5.0,
            "protein folding": 4.0, "protein": 2.5,
            "rna": 3.5, "mrna": 4.0, "nucleotide": 4.5,
            "amino acid": 3.5, "gene expression": 4.5,
            "genetic": 3.0, "genetics": 3.5, "genotype": 4.0,
            "phenotype": 3.5, "mutation": 3.0, "allele": 4.0,
            "chromosome": 4.0, "chromatin": 4.5,
            "transcription": 3.0, "translation": 2.0,
            "polymerase": 4.5, "pcr": 4.0, "primer": 3.5,
            "sequencing": 3.5, "next-generation sequencing": 5.0,
            "epigenetic": 4.5, "methylation": 4.5,
            "double helix": 5.0, "base pair": 4.5,
            "plasmid": 4.5, "recombinant": 4.0,
            "bioinformatic": 4.0, "molecular biology": 4.0,
            "cell": 1.5, "organism": 2.0, "biological": 2.0,
            "enzyme": 3.0, "helicase": 5.0, "ligase": 5.0,
        },
        "music_history": {
            "music": 3.0, "musical": 3.0, "musician": 3.5,
            "baroque": 5.0, "classical music": 5.0, "romantic era": 5.0,
            "sonata": 5.0, "symphony": 4.5, "concerto": 5.0,
            "opera": 4.0, "aria": 4.5, "oratorio": 5.0,
            "mozart": 5.0, "beethoven": 5.0, "bach": 4.5,
            "chopin": 5.0, "haydn": 5.0, "handel": 5.0,
            "wagner": 4.5, "vivaldi": 5.0, "schubert": 5.0,
            "polyphony": 5.0, "counterpoint": 5.0, "fugue": 5.0,
            "ethnomusicology": 5.0, "musicology": 5.0,
            "renaissance music": 5.0, "medieval music": 5.0,
            "harmony": 3.0, "melody": 3.0, "rhythm": 2.5,
            "composer": 4.5, "composition": 3.0, "orchestr": 4.0,
            "choir": 4.0, "choral": 4.5, "liturgical": 4.5,
            "jazz": 4.0, "blues": 3.5, "folk music": 4.0,
            "notation": 3.5, "score": 2.0, "tempo": 3.5,
            "instrument": 2.5, "piano": 3.5, "violin": 3.5,
            "conservatory": 4.5, "recital": 4.0,
        },
    }

def classify_document(text):
    if not text or not text.strip():
        return "music_history"
    text_lower = text.lower()
    keywords = get_category_keywords()
    scores = defaultdict(float)
    for category, kw_dict in keywords.items():
        for kw, weight in kw_dict.items():
            count = text_lower.count(kw)
            if count > 0:
                scores[category] += count * weight
    if not scores:
        return "music_history"
    best = max(scores, key=scores.get)
    return best

def create_category_folders(base_dir):
    for folder in CATEGORY_FOLDERS.values():
        os.makedirs(os.path.join(base_dir, folder), exist_ok=True)

def sort_files_into_folders(source_dir, dest_base_dir, extract_fn):
    results = {}
    files = [f for f in os.listdir(source_dir) if os.path.isfile(os.path.join(source_dir, f))]
    create_category_folders(dest_base_dir)
    for fname in files:
        fpath = os.path.join(source_dir, fname)
        text = extract_fn(fpath)
        category = classify_document(text)
        dest_dir = os.path.join(dest_base_dir, category)
        shutil.move(fpath, os.path.join(dest_dir, fname))
        results[fname] = category
    return results
