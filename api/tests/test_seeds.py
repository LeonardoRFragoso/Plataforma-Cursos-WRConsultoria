import os
import sys

import pytest

# Permite importar seed_db.py do diretório pai (api/)
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import seed_db


@pytest.mark.asyncio
async def test_seed_database():
    """Executa o script de seed e cobre os módulos em app/seeds."""
    await seed_db.main()
