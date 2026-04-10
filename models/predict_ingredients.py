"""
predict_ingredients.py
-----------------------
Predict ingredients from a food image using the trained im2recipe ResNet50 model.

Usage:
    python predict_ingredients.py --image path/to/image.jpg
    python predict_ingredients.py --image path/to/image.jpg --threshold 0.3 --topk 15
    python predict_ingredients.py --image path/to/image.jpg --model best_ingredient_model.pth --vocab my_vocab.pkl
"""

import argparse
import torch
import torch.nn as nn
from torchvision import models, transforms
from PIL import Image


# ── Config ────────────────────────────────────────────────────────────────────
DEFAULT_MODEL  = 'best_ingredient_model.pth'
DEFAULT_VOCAB  = 'my_vocab.pkl'
DEFAULT_THRESH = 0.28
DEFAULT_TOPK   = 10


# ── Transform ─────────────────────────────────────────────────────────────────
transform = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize([0.485, 0.456, 0.406],
                         [0.229, 0.224, 0.225])
])


# ── Load model & vocab from pth ───────────────────────────────────────────────
def load_model(model_path, device):
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

    print(f"Loaded model with vocab size: {len(vocab)}")
    return model, vocab, idx_to_ing


# ── Predict ───────────────────────────────────────────────────────────────────
def predict_ingredients(image_path, model, idx_to_ing, device,
                        threshold=DEFAULT_THRESH, topk=DEFAULT_TOPK):
    # Load image
    try:
        img = Image.open(image_path).convert('RGB')
    except Exception as e:
        raise ValueError(f"Could not open image: {e}")

    tensor = transform(img).unsqueeze(0).to(device)

    # Run inference
    with torch.no_grad():
        probs = torch.sigmoid(model(tensor)).squeeze().cpu()

    # Top K above threshold
    top_probs, top_idx = torch.topk(probs, topk)
    ingredients = [
        (idx_to_ing[i.item()], round(p.item(), 4))
        for p, i in zip(top_probs, top_idx)
        if p.item() > threshold
    ]

    return ingredients


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description='Predict ingredients from a food image')
    parser.add_argument('--image',     type=str, required=True,            help='Path to food image')
    parser.add_argument('--model',     type=str, default=DEFAULT_MODEL,    help='Path to model weights')
    parser.add_argument('--threshold', type=float, default=DEFAULT_THRESH, help='Probability threshold')
    parser.add_argument('--topk',      type=int, default=DEFAULT_TOPK,     help='Top K predictions')
    args = parser.parse_args()

    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Using: {device}")

    # Load model and vocab from pth
    model, vocab, idx_to_ing = load_model(args.model, device)

    # Predict
    print(f"Predicting for:      {args.image}")
    print(f"Threshold:           {args.threshold}")
    print(f"Top K:               {args.topk}")
    print("-" * 40)

    ingredients = predict_ingredients(
        image_path = args.image,
        model      = model,
        idx_to_ing = idx_to_ing,
        device     = device,
        threshold  = args.threshold,
        topk       = args.topk
    )

    if ingredients:
        print("Predicted ingredients:")
        for name, conf in ingredients:
            print(f"  {name}: {conf:.1%}")
    else:
        print("No ingredients found above threshold. Try lowering --threshold.")

    return [name for name, _ in ingredients]


if __name__ == '__main__':
    main()
