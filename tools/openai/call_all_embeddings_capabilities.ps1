# Test basique
python tools/openai/openai_call_embeddings.py `
       --input "Hello, world!" `
       --env-file ..\.env


# Test avec modèle spécifique et dimensions
 python tools/openai/openai_call_embeddings.py `
        --input "AI is transforming the world" `
        --dimensions 1024 `
        --model text-embedding-3-large `
        --env-file ..\.env

# Test avec fichier d'entrées multiples
python tools/openai/openai_call_embeddings.py `
       --input-file .\tools\tests_data\texts.txt `
       --test-multiple `
       --env-file ..\.env

# Test format base64
python tools/openai/openai_call_embeddings.py `
       --input "Base64 encoding test" `
       --format base64 `
       --env-file ..\.env

# Test tous les formats
python tools/openai/openai_call_embeddings.py `
       --input "Test all formats" `
       --test-formats `
       --env-file ..\.env

# Test toutes les dimensions (pour modèles text-embedding-3)
python tools/openai/openai_call_embeddings.py `
       --model text-embedding-3-large `
       --test-dimensions `
       --env-file ..\.env

# Mode verbose avec vecteurs affichés
python tools/openai/openai_call_embeddings.py `
       --input "Verbose mode test" `
       --verbose `
       --env-file ..\.env