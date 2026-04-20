"""
Module for ingredient prediction model utility functions.
"""
import io
import base64

import torch
import torch.nn as nn
from torchvision import models, transforms
from PIL import Image

# ── Config ────────────────────────────────────────────────────────────────────
DEFAULT_THRESH = 0.28
DEFAULT_TOPK   = 10

# ── Transform ─────────────────────────────────────────────────────────────────
transform = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize([0.485, 0.456, 0.406],
                         [0.229, 0.224, 0.225])
])


def load_model(model_path, device='cpu'):
    """
    Load pytorch model from path
    """
    checkpoint = torch.load(model_path, map_location=device, weights_only=False)

    # Load vocab from checkpoint
    vocab      = checkpoint['vocab']
    idx_to_ing = {v: k for k, v in vocab.items()}

    # Build model
    model    = models.resnet50()
    model.fc = nn.Linear(2048, len(vocab))
    model.load_state_dict(checkpoint['state_dict'])
    model    = model.to(device)
    model.eval()

    return model, idx_to_ing

def predict_from_base64(
    contents, model, idx_to_ing, 
    device = 'cpu', 
    threshold: float = DEFAULT_THRESH, 
    topk: int = DEFAULT_TOPK
    ):
    """
    Core function for Dash callbacks.
    Takes the base64 string from dcc.Upload and returns a list of (ingredient, confidence).
    """

    if not contents:
        return []

    try:
        # Parse base64 string
        content_type, content_string = contents.split(',')
        decoded = base64.b64decode(content_string)
        
        # Convert to PIL Image
        img = Image.open(io.BytesIO(decoded)).convert('RGB')
        
        # Preprocess
        tensor = transform(img).unsqueeze(0).to(device)

        # Inference
        with torch.no_grad():
            probs = torch.sigmoid(model(tensor)).squeeze().cpu()

        # Extract results
        top_probs, top_idx = torch.topk(probs, min(topk, len(probs)))
        
        ingredients = [
            (idx_to_ing[i.item()], round(p.item(), 4))
            for p, i in zip(top_probs, top_idx)
            if p.item() > threshold
        ]
        
        return ingredients
    
    except Exception as e:
        return []