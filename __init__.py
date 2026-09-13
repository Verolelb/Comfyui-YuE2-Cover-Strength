from .abc_cover_strength import YuE2CoverStrength
from .yue2_instrumental import YuE2Instrumental

# Enregistrement des deux nœuds auprès de ComfyUI
NODE_CLASS_MAPPINGS = {
    "YuE2CoverStrength": YuE2CoverStrength,
    "YuE2Instrumental": YuE2Instrumental,
}

# Noms lisibles affichés dans le menu d'ajout de nœud
NODE_DISPLAY_NAME_MAPPINGS = {
    "YuE2CoverStrength": "YuE2 Cover Strength",
    "YuE2Instrumental": "YuE2 Instrumental",
}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]