# Test basique
python tools/openai/openai_call_embeddings.py --input "Hello, world!"

# Test avec modèle spécifique et dimensions
 python tools/openai/openai_call_embeddings.py --input "AI is transforming the world" --dimensions 1024 --model text-embedding-3-large

# Test avec fichier d'entrées multiples
python tools/openai/openai_call_embeddings.py --input-file .\tools\tests_data\texts.txt --test-multiple

# Test format base64
python tools/openai/openai_call_embeddings.py --input "Test embedding" --encoding-format base64

# Test tous les formats
python tools/openai/openai_call_embeddings.py --input "Comprehensive test" --test-formats

# Test toutes les dimensions (pour modèles text-embedding-3)
python tools/openai/openai_call_embeddings.py --model text-embedding-3-large --test-dimensions

# Mode verbose avec vecteurs affichés
python tools/openai/openai_call_embeddings.py --input "Debug mode" --show-vectors --verbose