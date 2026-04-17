import re
import sys

def update_css_content(content):
    # 1. Update Fonts
    content = content.replace("family=Inter:wght@400;500;600;700&family=Manrope:wght@400;500;600;700;800", "family=Space+Grotesk:wght@400;500;600;700&family=Space+Mono:wght@400;700&family=Outfit:wght@400;500")
    
    # 2. Update variables in :root
    root_replacements = {
        "--surface: #0b1326;": "--surface: #050505;",
        "--surface-container-lowest: #060e20;": "--surface-container-lowest: #000000;",
        "--surface-container-low: #131b2e;": "--surface-container-low: #121212;",
        "--surface-container: #171f33;": "--surface-container: #18181A;",
        "--surface-container-high: #222a3d;": "--surface-container-high: #27272A;",
        "--surface-container-highest: #2d3449;": "--surface-container-highest: #3F3F46;",
        "--surface-bright: #31394d;": "--surface-bright: #52525B;",
        "--primary: #adc6ff;": "--primary: #FF4500;",
        "--primary-container: #4d8eff;": "--primary-container: #EAB308;",
        "--secondary: #4edea3;": "--secondary: #10B981;",
        "--secondary-container: #00311f;": "--secondary-container: #064E3B;",
        "--tertiary: #c0c1ff;": "--tertiary: #60A5FA;",
        "--on-surface: #dae2fd;": "--on-surface: #FAFAFA;",
        "--on-surface-variant: #c2c6d6;": "--on-surface-variant: #A1A1AA;",
        "--outline-variant: #424754;": "--outline-variant: #333333;",
        "--error: #ffb4ab;": "--error: #EF4444;",
        "--success: #28a745;": "--success: #22c55e;",
        "--font-display: 'Manrope', sans-serif;": "--font-display: 'Space Grotesk', sans-serif;\n    --font-mono: 'Space Mono', monospace;",
        "--font-body: 'Inter', sans-serif;": "--font-body: 'Outfit', sans-serif;",
        "--radius-sm: 6px;": "--radius-sm: 0px;",
        "--radius-md: 12px;": "--radius-md: 0px;",
    }
    
    for old, new in root_replacements.items():
        content = content.replace(old, new)
        
    # 3. Update styling elements
    # Remove box-shadow blurs and backdrop-filters
    content = re.sub(r'box-shadow:.*?;', 'box-shadow: none;', content)
    content = re.sub(r'backdrop-filter:.*?;', 'backdrop-filter: none;', content)
    content = re.sub(r'-webkit-backdrop-filter:.*?;', '', content)
    
    # Add harsh borders
    content = content.replace("border: none;", "border: 1px solid var(--outline-variant);")
    
    # Replace gradients with solid brutalist blocks
    content = re.sub(r'background: linear-gradient.*?;', 'background: var(--primary); color: #000;', content)
    
    # Task dots use square instead of round
    content = content.replace("border-radius: 50%;", "border-radius: 0;")
    
    # Active timer neon effect
    content = content.replace("-webkit-text-fill-color: transparent;", "color: var(--primary);")
    content = content.replace("-webkit-background-clip: text;", "")
    content = content.replace("background: linear-gradient(135deg, var(--primary), var(--primary-container));", "")
    
    # Change specific timer class font
    content = content.replace(".timer {\n    font-family: var(--font-display);", ".timer {\n    font-family: var(--font-mono);")
    
    # Harsh box shadows for buttons on hover
    content = content.replace('.auth-actions button[onclick="signInWithGoogle()"]:hover, \n.auth-actions button[onclick="signInWithPassword()"]:hover {\n    box-shadow: inset 0 0 0 2px rgba(173, 198, 255, 0.5);\n    filter: brightness(1.1);\n}', '.auth-actions button[onclick="signInWithGoogle()"]:hover, \n.auth-actions button[onclick="signInWithPassword()"]:hover {\n    box-shadow: 4px 4px 0 var(--on-surface);\n    transform: translate(-2px, -2px);\n    filter: brightness(1.1);\n}')
    content = content.replace("transition: all 0.2s ease;", "transition: all 0.1s linear;")
    
    # Cards hover
    content = content.replace("transition: background 0.2s ease;", "transition: all 0.1s linear;\n    border: 1px solid var(--outline-variant);")
    content = content.replace(".tasks li:hover {\n    background: var(--surface-bright);\n}", ".tasks li:hover {\n    background: var(--surface-bright);\n    border-color: var(--on-surface);\n    box-shadow: 4px 4px 0 var(--on-surface);\n    transform: translate(-2px, -2px);\n}")

    # Titles
    content = content.replace('/* The Midnight Architect - Design System */', '/* Industrial Neobrutalism - Design System */')
    
    return content

def main():
    try:
        # Update styles.css
        with open('styles.css', 'r') as f:
            css_content = f.read()
            
        modified_css = update_css_content(css_content)
        
        with open('styles.css', 'w') as f:
            f.write(modified_css)
            
        # Update index.html which contains both the CSS and head tags
        with open('index.html', 'r') as f:
            html_content = f.read()
            
        modified_html = update_css_content(html_content)
        
        with open('index.html', 'w') as f:
            f.write(modified_html)
            
        print("Successfully updated design system in styles.css and index.html")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
