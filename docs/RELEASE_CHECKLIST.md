# BlenDAZ Release Checklist

## Marketplaces

### Superhive (formerly Blender Market)
- Primary storefront — built-in audience of Blender buyers
- Apply as Creator at superhivemarket.com (requires portfolio link — GitHub works)
- Curated: every addon reviewed by Blender experts before going live
- **Fees**: Free tier keeps 70%. Paid tiers: 80-90%.
- Must be GPL or MIT licensed
- Packaging: ZIP with `blender_manifest.toml` (Blender 4.2+ extensions format)
- Assets: featured image (no Blender logo), 4-6 screenshots, demo video, detailed description
- Quarterly 25% off sales events available to participate in

### Gumroad
- Secondary storefront — best for direct-link sales from your own marketing
- No approval process, no monthly fees
- **Fees**: 10% + $0.50 per direct sale. 30% via Gumroad Discover.
- Handles global VAT/GST/sales tax as Merchant of Record (since Jan 2025)
- Built-in license keys auto-generated per purchase, verifiable via API
- Assets: cover image (1280x720), thumbnail (600x600), description, tags

### Blender Extensions Platform (extensions.blender.org)
- Free GPL version only — no paywalls allowed
- Appears inside Blender preferences when users browse extensions
- Highest-intent discovery channel — built right into Blender
- Good for a lite/free version that funnels to the paid version

---

## Pricing

### Comparable Addons
| Addon | Price | Category |
|-------|-------|----------|
| Auto-Rig Pro | $37-50 | Rigging (#1 bestseller) |
| Hard Ops + Boxcutter | $28-38 | Modeling |
| X-Pose Picker | $23-35 | Pose picking |
| Human Generator | $68-128 | Character creation |
| Diffeomorphic DAZ Importer | Free | DAZ import (not posing) |

### Recommended
- **Launch price**: $29-35 with 20% introductory discount (first 2-4 weeks)
- DAZ posing niche is underserved — clear value proposition

### Free / Lite Version Strategy
**Free version** (Blender Extensions Platform + Gumroad $0):
- Basic bone selection and posing
- Single character support
- Core Touch functionality

**Paid version** (Superhive + Gumroad):
- Multi-character support
- Full PoseBridge (body, face, hands panels)
- IK behavior and proximity overrides
- Streamline mode
- Mannequin, outline, camera setup
- Priority support and updates

---

## Technical Packaging

### Pre-Release Code Cleanup
- [ ] GPL license header on every Python file
- [ ] LICENSE file in package root
- [ ] Remove debug prints and development-only code
- [ ] Clean up unused imports
- [ ] Version number set consistently

### Blender Extension Format (4.2+)
- [ ] Create `blender_manifest.toml` with required fields:
  - `schema_version` = "1.0.0"
  - `id` = unique identifier (e.g. "blendaz")
  - `version` = semantic version (e.g. "1.0.0")
  - `name` = "BlenDAZ"
  - `tagline` = short description
  - `maintainer` = name + email
  - `type` = "add-on"
  - `blender_version_min` = minimum supported version
- [ ] All files in a single top-level folder named after the extension `id`
- [ ] Use relative imports throughout
- [ ] Replace module name references with `__package__`
- [ ] No write access to own folder assumed
- [ ] External deps as Python Wheels (if any)

### ZIP Structure
```
blendaz.zip
  blendaz/
    __init__.py
    blender_manifest.toml
    LICENSE
    core.py
    panel_ui.py
    daz_bone_select.py
    streamline.py
    extract_hands.py
    extract_face.py
    ... (all other .py files)
```

### Testing
- [ ] Test install from ZIP on clean Blender (target versions)
- [ ] Test with Genesis 8 Female, Genesis 8 Male, Genesis 8.1 Female, Genesis 8.1 Male
- [ ] Test with custom-sized characters (scaled morphs)
- [ ] Test multi-character registration and switching
- [ ] Test all PoseBridge modes (body, hands, face)
- [ ] Test Streamline on/off
- [ ] Test IK on all limbs
- [ ] Verify clean uninstall (no leftover properties or handlers)

---

## Marketing Assets

### Required
- [ ] Cover image / featured image (1280x720+, no Blender logo in image)
- [ ] 4-6 product screenshots showing key features
- [ ] Demo video — short reel (60-90 sec) + longer tutorial (5-10 min)
- [ ] Product description (benefits-first, then features, compatibility, refund policy)
- [ ] Tags: "Blender addon", "DAZ", "posing", "character", "IK", "animation", "rigging"

### Product Description Structure
1. **The Big Idea** — What is BlenDAZ? (one-liner)
2. **The Problem** — Posing DAZ characters in Blender is tedious and unintuitive
3. **The Promise** — Pose any DAZ character intuitively with click-to-bone, IK, and PoseBridge panels
4. **Unique Features** — What makes it different (proximity bone detection, multi-character, face/hand panels, Streamline)
5. **How It Works** — Brief workflow description
6. **Compatibility** — Blender versions, DAZ Genesis versions, Diffeomorphic requirement
7. **What's Included** — Feature list for free vs paid

---

## Launch Channels

### Community (Free)
| Channel | Action |
|---------|--------|
| **BlenderArtists** | Product thread in Promotions category (ranks well on Google) |
| **Reddit** | r/blender (2M+ subs), r/daz3d, r/blenderaddons — demo GIFs, follow 90/10 rule |
| **DAZ Forums** | Users actively discuss Blender posing frustrations — direct audience |
| **YouTube** | Demo reel + tutorial, tags: #b3d #blender #daz3d |
| **Twitter/X** | Short GIF clips of posing workflows, #b3d #blender #daz3d |
| **Discord** | Blender official, Daz3D Slackers, Diffeomorphic community |
| **blender-addons.org** | Submit listing for long-term SEO (free for free addons, 10% for paid) |

### Paid (Optional)
| Channel | Cost | Notes |
|---------|------|-------|
| **BlenderNation** | EUR 100+ | 150K impressions, promoted posts |

### Pre-Launch (4-8 weeks before)
- [ ] Post WIP GIFs/videos on Twitter, Reddit, BlenderArtists
- [ ] Collect emails via free Gumroad "notification" product
- [ ] Recruit 5-15 beta testers from DAZ/Blender communities
- [ ] Prepare documentation

### Launch Day
- [ ] Publish on Superhive + Gumroad simultaneously
- [ ] Post to all community channels
- [ ] Launch on Tuesday or Wednesday (Superhive recommendation)

### Post-Launch
- [ ] Respond to every support request quickly
- [ ] Regular updates with changelogs
- [ ] Participate in Superhive quarterly sales
- [ ] Monitor and engage with community threads

---

## License Key / Copy Protection (Optional)

Gumroad auto-generates license keys per purchase. Verification via API:

```
POST https://api.gumroad.com/v2/licenses/verify
  product_id: <your_product_id>
  license_key: <customer_key>
  increment_uses_count: true
```

**Pragmatic approach**: Use license keys as "keep honest people honest" — Blender addons are Python source, no DRM is bulletproof. Consider a grace period / offline fallback. Store key in `bpy.types.AddonPreferences`.

---

## Superhive Creator Application Checklist
- [ ] Valid personal information (name, contact)
- [ ] Portfolio link (GitHub repo with README and screenshots)
- [ ] Product proposal describing addon category and pricing range
- [ ] PayPal or Stripe for payouts
- [ ] Have a ready-to-upload product (not "still in development")
