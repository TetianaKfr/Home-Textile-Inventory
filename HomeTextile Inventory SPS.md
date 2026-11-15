# Software Requirements Specification (SRS)

# Home Textile Inventory and AI Matching Application

**Document type:** Product Requirements and Technical Specification
**Project name:** Home Textile Inventory
**Document status:** Initial consolidated specification
**Target platforms:** iOS, Android, Web Browser, Desktop Web

Source: `Home Textile Inventory SRS.pdf`

The rules below follow the current application. Search and filters live on the inventory. Each physical unit keeps its own place. A room or storage location that still holds items cannot be deleted. A negative measurement is never treated as a size.

## 1. Project Overview

### 1.1. Purpose

The purpose of the application is to help individuals and families manage, organize, search, and combine their home textiles and related household items.

The application will provide a centralized cloud-based inventory of textiles and household objects stored across multiple homes, rooms, cupboards, shelves, drawers, and storage boxes.

Users will be able to:

- Create and maintain a detailed inventory of home textiles.
- Record the dimensions, colors, materials, patterns, and other properties of each item.
- Attach multiple photographs to each inventory item.
- Organize items by home and storage location.
- Add and manage multiple users with different access permissions.
- Search and filter the inventory using multiple criteria.
- Use AI to identify items and suggest their attributes from photographs.
- Use AI to find compatible textile combinations based on dimensions and visual appearance.
- Create and save complete bedding and table-setting combinations.
- Find items quickly, including items stored in different homes.

The application must work consistently across mobile devices and computers, using one shared cloud database.

### 1.2. Main Product Concept

The application should function as a smart household textile inventory rather than a simple photo catalogue.

It must understand relationships between objects and textiles.

For example:

- A bed requires a suitable mattress protector, fitted or flat sheet, duvet, duvet cover, pillows, and pillowcases.
- A table requires a suitably sized tablecloth.
- A window requires appropriately sized curtains.
- A pillow can be matched with a suitable pillowcase or protective cover.
- A duvet can be matched with a compatible duvet cover.

The system should be able to identify suitable combinations using both technical dimensions and visual compatibility.

## 2. Supported Platforms and Users

### 2.1. Supported Platforms

The application must support:

- iOS smartphones and tablets.
- Android smartphones and tablets.
- Desktop and laptop computers.
- Web browsers.

All platforms must use the same database and business logic.

Changes made on one device must synchronize with the other devices.

### 2.2. Multiple Users

The application must support multiple users within one shared household or family group.

All authorized members of a family group should be able to access the shared inventory according to their permissions.

### 2.3. User Roles and Permissions

The initial permission model should include three roles:

| Role | Permissions |
| --- | --- |
| Administrator | Full access to all data, users, settings, and inventory |
| Editor | Add, edit, move, and manage inventory items. Delete an empty room or storage location. A home can be deleted only by an administrator |
| Viewer | View inventory, search, filter, and inspect item details |

The system must support:

- Creating a family group.
- Inviting users by email.
- Accepting and managing invitations.
- Assigning and changing user roles.
- Removing users from a family group.
- Revoking access.
- Maintaining data ownership and access permissions.

All permissions must be enforced on the server side, not only in the user interface.

## 3. Application Structure

The main navigation contains the following sections:

1. Dashboard
2. Inventory, including the catalogue, search, and filters
3. Add Item
4. AI Matching
5. Storage Locations
6. Beds, tables, and windows
7. Saved Sets
8. Family
9. Settings

Search is not a separate screen. An address that still points at search opens the inventory and keeps the same filters.

Beds, mattresses, tables, and windows share one section. The exact navigation layout may differ between mobile and desktop versions, but all major functions must remain available.

### 3.1. Dashboard

The dashboard should provide a quick overview of the household inventory.

Suggested information:

- Total number of inventory items.
- Number of items by category.
- Items currently in use.
- Items in storage.
- Items in laundry.
- Recently added items.
- Recently moved items.
- Recently created combinations.
- Quick access to search and AI matching.

## 4. Inventory Categories

The application must support the following initial categories.

### 4.1. Textile Categories

#### Bedding and bedroom textiles

- Bed sheets
- Fitted sheets
- Duvet covers
- Pillowcases
- Pillow protectors
- Mattress protectors
- Blankets
- Duvets
- Pillows
- Bedspreads
- Other bedding accessories

#### Bathroom textiles

- Bath towels
- Hand towels
- Face towels
- Bath mats
- Other bathroom textiles

#### Window and interior textiles

- Curtains
- Drapes
- Sheer curtains
- Other window textiles

#### Dining textiles

- Tablecloths
- Table runners
- Placemats
- Other dining textiles

#### Other household textiles

- Other textile items, with the possibility of creating custom categories.

### 4.2. Related Household Objects

The application must also support objects to which textiles can be matched:

- Beds
- Mattresses
- Pillows
- Tables
- Windows
- Other configurable household objects.

Beds, tables, and windows are not necessarily textile inventory items. They are reference objects used for measurements, storage organization, and AI matching.

### 4.3. Custom Categories

The system should allow administrators to add custom categories and define their properties without requiring a major software redesign.

## 5. Item Records and Attributes

Each inventory item must have an individual record.

### 5.1. General Item Information

Each item record should support:

- Unique item ID.
- Category.
- Item name.
- Description.
- Brand or manufacturer.
- Quantity.
- Main color.
- Additional colors.
- Pattern or design.
- Texture.
- Material or fabric composition.
- Dimensions.
- Seasonality.
- Current status.
- Photographs.
- Home and storage location.
- Notes and comments.
- Date added.
- Date last updated.
- Item history.

Not every field must be mandatory.

The available fields must depend on the selected category.

### 5.2. Dimensions

Dimensions must be stored in centimeters.

The system must support:

- Width.
- Length.
- Height.
- Diameter.
- Mattress depth.
- Other category-specific measurements.

The interface should display dimensions in a consistent format, such as:

Width × Length × Height

The system must accept different user input formats, including:

- 140 × 190
- 140 x 190
- 140/190
- 140 by 190
- 140 на 190

The application must normalize these values into a consistent internal format.

When an item’s dimensions are entered as a pair, the first number is stored as width and the second as length. The application does not swap them on save.

A size used only as a search filter may match the same two numbers in either order. See section 11.

Zero is a valid measurement. A negative number is not a measurement. It is not saved on a bed, mattress, table, or window, and compatibility calculations ignore it. A recommended size, an explanation, or a warning must not show a negative number.

### 5.3. Colors

Each item must support:

- One primary color.
- Multiple secondary colors.
- Optional color descriptions.
- AI-assisted color identification from photographs.

AI should identify approximate colors and allow the user to confirm or correct them.

Color recognition must not be treated as an exact measurement. Lighting, shadows, and camera settings can affect the result.

### 5.4. Patterns and Materials

The user should be able to select or enter:

- Plain.
- Striped.
- Checked.
- Floral.
- Geometric.
- Abstract.
- Printed.
- Embroidered.
- Textured.
- Other patterns.

Material examples:

- Cotton.
- Linen.
- Polyester.
- Satin.
- Silk.
- Wool.
- Microfiber.
- Bamboo fabric.
- Mixed composition.
- Unknown.

The application must allow custom values.

AI may suggest a pattern or material based on a photograph, but it must clearly distinguish visual estimates from confirmed information.

## 6. Category-Specific Attributes

Different categories require different attributes.

### 6.1. Sheets

Required or optional fields:

- Width.
- Length.
- Sheet type: flat or fitted.
- Fitted sheet elastic configuration.
- Mattress depth compatibility.
- Color.
- Pattern.
- Material.

For fitted sheets, the system must record the maximum mattress depth or fitted corner height where available.

For flat sheets, the system should consider the desired overhang on each side of the mattress.

### 6.2. Duvet Covers

Fields:

- Width.
- Length.
- Closure type.
- Color.
- Pattern.
- Material.
- Seasonality.

Closure types may include:

- Buttons.
- Zipper.
- Ties.
- Envelope closure.
- Other.

### 6.3. Pillowcases

Fields:

- Width.
- Length.
- Closure type.
- Color.
- Pattern.
- Material.

### 6.4. Pillow Protectors

Fields:

- Width.
- Length.
- Height or depth, if relevant.
- Closure type.
- Material.
- Color.

### 6.5. Duvets

Fields:

- Width.
- Length.
- Thickness or loft.
- Season.
- Filling type.
- Warmth level.
- Weight, if known.
- Color.
- Brand.

Seasonal options:

- Summer.
- Winter.
- Spring/Autumn.
- All-season.

Filling types may include:

- Down.
- Feather.
- Wool.
- Cotton.
- Synthetic.
- Microfiber.
- Other.
- Unknown.

### 6.6. Pillows

Fields:

- Width.
- Length.
- Height or loft.
- Filling type.
- Firmness.
- Shape.
- Weight, if known.
- Brand.

### 6.7. Mattress Protectors

Fields:

- Width.
- Length.
- Mattress depth.
- Attachment type.
- Material.
- Waterproof properties, if applicable.
- Color.

### 6.8. Curtains

Fields:

- Panel width.
- Curtain length or height.
- Number of panels.
- Heading or attachment type.
- Fabric type.
- Color.
- Pattern.
- Transparency.
- Lining.
- Recommended fullness ratio, if known.

Attachment types may include:

- Eyelets.
- Loops.
- Curtain tape.
- Hooks.
- Rings.
- Other.

### 6.9. Tablecloths

Fields:

- Shape.
- Width.
- Length.
- Diameter.
- Material.
- Color.
- Pattern.
- Desired overhang, if known.

Shapes:

- Rectangular.
- Square.
- Round.
- Oval.
- Custom.

### 6.10. Blankets and Bedspreads

Fields:

- Width.
- Length.
- Thickness.
- Material.
- Seasonality.
- Filling, if applicable.
- Color.
- Pattern.

### 6.11. Beds and Mattresses

Fields:

- Object name.
- Bed type.
- Sleeping area width.
- Sleeping area length.
- Mattress width.
- Mattress length.
- Mattress depth or height.
- Photographs.
- Home and room location.
- Notes.

### 6.12. Tables

Fields:

- Table name.
- Table type.
- Shape.
- Width.
- Length.
- Diameter.
- Height.
- Photographs.
- Home and room location.
- Notes.

Table types may include:

- Dining table.
- Coffee table.
- Side table.
- Console table.
- Other.

Shapes may include:

- Rectangular.
- Square.
- Round.
- Oval.
- Custom.

### 6.13. Windows

Fields:

- Window name or identifier.
- Width.
- Height.
- Number of panels or sections.
- Window type.
- Photographs.
- Home and room location.
- Curtain rail or track type.
- Curtain attachment requirements.
- Notes.

For curtain matching, the application must also support:

- Curtain rail width.
- Height from the rail to the floor.
- Height from the rail to the windowsill, if applicable.
- Desired curtain length.
- Desired fullness ratio.
- Number of curtain panels.

Window dimensions and curtain rail dimensions must be stored separately.

## 7. Photographs and Image Management

### 7.1. Multiple Photographs

Each item must support multiple photographs.

Users should be able to:

- Take a photograph using the device camera.
- Upload an existing photograph.
- Add several photographs to one item.
- Delete or replace photographs.
- Select a main photograph.
- View photographs in a gallery.

Photographs must be stored in cloud storage and linked to the relevant inventory record.

### 7.2. AI-Assisted Item Recognition

The user must be able to create an item by uploading a photograph.

The AI should attempt to identify:

- Item category.
- Likely item type.
- Main color.
- Secondary colors.
- Pattern.
- Texture.
- Possible material.
- Other visually identifiable properties.

The AI should then present a suggested item form with the identified fields filled in.

The user must be able to:

- Accept the suggestions.
- Edit individual fields.
- Reject incorrect suggestions.
- Complete missing information manually.
- Save the item.

**Important:** AI must not invent measurements, fabric composition, brand names, or other information that cannot reliably be identified from the photograph.

Unknown information must remain blank or be marked as unconfirmed.

The application should clearly distinguish between:

- User-confirmed information.
- AI-generated suggestions.
- Unknown information.

## 8. Storage and Location Management

The application must support an unlimited or practically unrestricted number of homes and storage locations, subject to the chosen infrastructure limits.

### 8.1. Location Hierarchy

The initial location hierarchy should be:

**Family Group → Home → Room → Storage Unit → Shelf / Drawer / Box**

Examples:

- Home 1
  - Bedroom
    - Wardrobe
      - Shelf 1
      - Shelf 2
      - Box 1
  - Bathroom
    - Cabinet
      - Drawer 1
- Home 2
  - Guest Room
    - Wardrobe
    - Box 4

Users should be able to create custom storage location types.

The hierarchy should support flexible nesting rather than being restricted to a fixed number of levels.

### 8.2. Location Management

Users must be able to:

- Add, edit, and delete locations.
- Move items between locations.
- View all items in a selected location.
- Search by home, room, cupboard, shelf, drawer, or box.
- View the full location path on an item record.

The system must retain a history of item movements.

An editor can delete a room or a storage location. Deleting a home stays limited to an administrator.

A room that still holds an active item cannot be deleted. The application asks the user to move the items out first. When the room no longer holds items, deleting it archives the room and every storage location inside it, and clears that room from beds, tables, and windows that used it.

A storage location that still holds an active item, including in a nested child, cannot be deleted. The application asks the user to move the items out first. Deleting an empty location archives that location and every nested location under it.

A nested location must remain in the same room as its parent.

Each physical unit records its place as separate facts: home, room, the storage it sits inside, location type, and location name, together with the full path. A card shows the place as home / room / location name. The item detail shows the home, the room, the containing storage, and the type separately. A unit with no location is shown as having no location.

### 8.3. QR Codes

The application should support optional QR codes for storage boxes.

A QR code is available only when the location type is box. A shelf, drawer, or cupboard does not show a QR image.

Each QR code should identify a specific location.

When a user scans a QR code, the application should display:

- Location name.
- Full location path.
- Items stored there.
- Item photographs.
- Item quantities.
- Item details.

The user should be able to move items into or out of the scanned location.

### 8.4. Location Accuracy

An individual physical item must have a clear current location.

If identical items are stored in different places, the system must be able to track their locations separately.

When an item is edited, each physical unit has its own location. A new item chooses one location for the units created with it. The location may be left empty.

## 9. Item Quantities and Individual Units

The application must distinguish between a general item record and individual physical units when necessary.

### 9.1. Recommended Data Structure

Use two related concepts:

**Item:** A general product or item definition.

**Item Unit:** An individual physical instance of that item.

Example:

A household has six identical white towels.

The general item record may describe:

- White bath towel.
- 70 × 140 cm.
- Cotton.
- Quantity: 6.

However, if the towels are stored in different locations or have different statuses, each physical unit must be tracked separately.

For example:

- Unit 1: Home 1, Bathroom cupboard.
- Unit 2: Home 1, Bathroom cupboard.
- Unit 3: Home 1, Laundry.
- Unit 4: Home 2, Guest room.
- Unit 5: Home 2, Wardrobe.
- Unit 6: Home 2, In use.

The application must not assign one shared location or status to multiple physical units when their actual locations or statuses differ.

Individual units should also be able to have their own photographs and attributes where necessary.

## 10. Item Status and History

Each physical item or unit should support the following statuses:

- Available.
- In use.
- In laundry.
- Temporarily unavailable.
- Damaged.
- Archived.

The exact status list may be configurable.

### 10.1. Item History

The application must record significant changes, including:

- Item creation.
- Attribute changes.
- Location changes.
- Status changes.
- Quantity changes.
- Photograph changes.
- Item archival.

Each history entry should include:

- Item ID.
- Action type.
- Previous value, where applicable.
- New value, where applicable.
- User who performed the action.
- Date and time.

This history should help users understand where an item was previously stored and who changed its details.

## 11. Search and Filtering

The application must provide a powerful search function across the entire inventory.

Search and the combined filters are part of the inventory catalogue. There is no separate search screen.

### 11.1. Search Criteria

The inventory filters are free text, size, house, category, color, material, pattern, status, and seasonality. Results can be sorted by name, category, width, date added, or location.

Users must be able to search by:

- Category.
- Item name.
- Dimensions.
- Color.
- Secondary colors.
- Pattern.
- Material.
- Brand.
- Seasonality.
- Status.
- Quantity.
- Home.
- Room.
- Storage location.
- Date added.
- Other available attributes.

### 11.2. Combined Filters

Users must be able to apply multiple filters simultaneously.

Examples:

- All white pillowcases.
- All duvets measuring 220 × 200 cm.
- All winter duvets.
- All cotton towels.
- All items stored in Box 4.
- All fitted sheets compatible with a 160 × 200 cm mattress.
- All available curtains in a particular home.
- All tablecloths suitable for round tables.

The search system must combine filters using logical AND/OR behavior where appropriate.

A size filter is a width-then-length pair. Accepted separators are ×, x, /, by, and на, for example 220 × 200. A value that cannot be read is rejected, with a request to use that form, and the size filter is not applied.

An item matches a size when its width and length are each within 1 cm of the pair, or within 1 cm of the same pair written the other way around. An item with a missing width or length does not match a size filter. This orientation check applies only to search. Saved dimensions keep the order entered in section 5.2.

An item matches a house when at least one of its physical units is stored in that house.

### 11.3. Search Results

Search results should display:

- Photograph.
- Item name.
- Category.
- Dimensions.
- Main color.
- Quantity.
- Current status.
- Storage location, shown as home / room / location name when those facts exist.

Users should be able to open an item directly from the search results.

The interface should support sorting by name, category, dimensions, date added, and location.

## 12. AI Matching and Compatibility Engine

This is one of the application's core functions.

The AI matching system must help users identify which existing textiles can be used with a selected bed, mattress, pillow, duvet, table, or window.

### 12.1. Matching Principles

Matching must be performed in two stages.

#### Stage 1 — Technical Compatibility

The system checks whether the dimensions, type, shape, and intended use are compatible.

This stage should primarily use deterministic rules and measurements rather than visual AI.

#### Stage 2 — Visual Compatibility

AI evaluates whether the technically compatible items look good together.

It considers:

- Main colors.
- Secondary colors.
- Patterns.
- Fabric textures.
- Overall visual style.
- Photographs of the items.

The system must not present visually attractive combinations as technically compatible if their dimensions or intended use do not match.

### 12.2. Matching Relationships

The application must support the following relationships:

| Main object | Compatible textile |
| --- | --- |
| Bed / Mattress | Bed sheet |
| Mattress | Mattress protector |
| Bed / Sleeping space | Bedding set |
| Duvet | Duvet cover |
| Pillow | Pillowcase |
| Pillow | Pillow protector |
| Table | Tablecloth |
| Window | Curtains |

The relationship model should be configurable so that additional object-to-textile relationships can be added in the future without redesigning the entire system.

### 12.3. Bed and Bedding Matching

Example:

A user selects a bed with:

- Mattress size: 140 × 190 cm.
- Mattress depth: 20 cm.

The user has:

- One duvet: 220 × 200 cm.
- Two pillows: 60 × 60 cm.

The application should search for:

- Compatible sheets for the mattress.
- A compatible duvet cover for the duvet.
- Two compatible pillowcases.

The system should present complete possible combinations.

Each suggested combination should include:

- Item photographs.
- Item names.
- Dimensions.
- Colors.
- Materials, where known.
- Quantity.
- Current storage location.
- Technical compatibility.
- Visual compatibility.
- Explanation of the recommendation.

The user should be able to compare several possible combinations.

### 12.4. Duvet and Duvet Cover Compatibility

The application should compare duvet dimensions with duvet cover dimensions.

Exact matches should receive the highest technical compatibility.

The system may also support configurable tolerances and manufacturer recommendations.

It must not assume that every difference in dimensions is automatically acceptable.

If the dimensions are uncertain or potentially unsuitable, the application should display a warning.

### 12.5. Mattress and Sheet Compatibility

For fitted sheets, the system must consider:

- Mattress width.
- Mattress length.
- Mattress depth.
- Fitted corner height.

For flat sheets, the system should consider:

- Mattress width.
- Mattress length.
- Desired side overhang.
- Desired head and foot overhang.

The system should calculate recommended sheet dimensions based on the selected mattress and user preferences.

### 12.6. Pillow and Pillowcase Compatibility

The application must compare:

- Pillow width.
- Pillow length.
- Pillow shape.
- Pillowcase width.
- Pillowcase length.

The system should distinguish between exact matches and acceptable manufacturer-recommended allowances.

### 12.7. Table and Tablecloth Compatibility

The system must support matching tablecloths to tables based on shape and dimensions.

The main calculation is:

#### Rectangular table

Tablecloth width = Table width + 2 × desired overhang.

Tablecloth length = Table length + 2 × desired overhang.

Example:

- Table: 90 × 160 cm.
- Desired overhang: 25 cm on each side.
- Recommended tablecloth: 140 × 210 cm.

#### Round table

Tablecloth diameter = Table diameter + 2 × desired overhang.

Example:

- Table diameter: 100 cm.
- Desired overhang: 25 cm.
- Recommended tablecloth diameter: 150 cm.

The application must also support square and oval tables.

For oval tables, the system should compare the relevant dimensions and shape.

The user should be able to set a preferred overhang.

If the user has not specified an overhang, the application may suggest a default value, but it must clearly identify it as a suggestion.

The shape labels carré and carre mean square when a table is compared with a tablecloth.

### 12.8. Window and Curtain Compatibility

Curtain matching must consider more than window dimensions.

The system must distinguish between:

- Window width.
- Window height.
- Curtain rail or track width.
- Desired curtain length.
- Height from the rail to the floor or windowsill.
- Number of curtain panels.
- Curtain attachment type.
- Desired fullness ratio.

#### Curtain width calculation

Recommended total curtain fabric width = Curtain rail width × Fullness ratio.

The system should support configurable fullness ratios, depending on curtain type and fabric.

For example:

- Curtain rail width: 200 cm.
- Fullness ratio: 2.0.
- Recommended total curtain fabric width: 400 cm.

If two panels are used, the recommended width per panel would be approximately 200 cm.

The application must check whether the available curtains have a suitable:

- Total width.
- Panel width.
- Length.
- Attachment type.

The application must not calculate curtain compatibility using only the window width when the curtain rail width is available.

### 12.9. Matching Results and Explanations

Each suggested combination should include:

- Technical compatibility score or status.
- Visual compatibility score or status.
- Explanation of why the items match.
- Any dimension discrepancies.
- Missing items.
- Storage location of each item.

The application should distinguish between:

- Exact technical match.
- Acceptable match.
- Possible match requiring user confirmation.
- Incompatible match.

Visual compatibility should be displayed separately from technical compatibility.

The system should offer multiple combinations, not only one result.

### 12.10. Missing Items

If the user selects a bed, table, or window and the inventory does not contain all required textiles, the application should identify what is missing.

For example:

- Compatible duvet found.
- Compatible duvet cover found.
- Compatible pillows found.
- No suitable pillowcases found.

The application should display the missing category and the required dimensions.

### 12.11. Measurements and place checks

A negative width, length, height, diameter, depth, overhang, rail width, desired curtain length, or fullness is rejected when a bed, mattress, table, or window is saved. The interface does not keep a negative number. Zero is allowed. An empty optional measurement is not stored.

Compatibility treats a negative measurement as missing. If a table has no usable width and length, or no usable diameter when it is round, the required tablecloth size asks for the table length and width. If a window has no usable rail width or window width, or no usable fullness, the required curtain width asks for the window width and the curtain length.

A bed, mattress, table, or window may name a room only together with a home, and that room must belong to the selected home.

## 13. Saved Sets and Combinations

Users must be able to save suggested or manually created combinations.

Examples:

- Main bedroom bedding set.
- Guest bedroom bedding set.
- Summer bedding set.
- Winter bedding set.
- Dining table set.
- Living room curtains.

Each saved set should include:

- Set name.
- Related bed, table, or window, where applicable.
- Selected inventory items or individual units.
- Photographs.
- Dimensions.
- Colors.
- Notes.
- Date created.
- Last updated.

A saved set should reference actual inventory items or physical units, rather than duplicating their data.

If an item is moved to another location, the saved set should still reference the same item and show its current location.

If an item becomes unavailable or is deleted, the application should indicate that the saved set needs attention.

## 14. Adding and Editing Items

The application must support two methods of adding inventory.

### 14.1. Manual Entry

The user selects a category and fills in the relevant fields.

The form must display only the attributes relevant to the selected category.

The user can add photographs and specify one storage location for the units created with the item. That location may be left empty.

### 14.2. AI-Assisted Entry

The user uploads or takes a photograph.

The AI analyzes the photograph and suggests:

- Category.
- Item type.
- Colors.
- Pattern.
- Texture.
- Possible material.
- Other visible properties.

The user reviews the suggestions, corrects them, enters missing details, and saves the item.

### 14.3. Editing

Users with sufficient permissions must be able to edit item details, including the storage location of each physical unit.

An item with one unit shows one location field. An item with several units shows one location field per unit.

Editing should not overwrite historical information without retaining an audit record.

### 14.4. Duplicate Detection

The application should attempt to identify possible duplicate records when a user adds a new item with similar photographs and attributes.

The system should ask the user whether to create a new item or update an existing record.

It must not automatically merge items without user confirmation.

## 15. Notifications and Data Synchronization

### 15.1. Cloud Synchronization

All inventory data must be stored in a shared cloud database.

Changes made by one authorized user should become visible to other authorized users.

### 15.2. Concurrent Editing

The system must prevent one user's changes from silently overwriting another user's changes.

If two users edit the same record simultaneously, the application should detect the conflict and provide a safe resolution process.

### 15.3. Offline Support

Offline access is recommended for mobile devices.

At a minimum, the application should allow users to view recently synchronized inventory data when offline.

If offline editing is implemented, changes must be synchronized when the device reconnects, with conflict handling.

### 15.4. Notifications

Optional notifications may be provided for:

- Invitations to a family group.
- Changes to shared inventory.
- Item movement, where enabled.
- Other important shared activity.

Notification settings should be configurable.

## 16. Data Model and Database Structure

The database should use a relational structure.

A recommended initial data model includes:

| Entity | Purpose |
| --- | --- |
| Users | User accounts and profile information |
| FamilyGroups | Shared household groups |
| FamilyGroupMembers | Membership and role assignments |
| Homes | Houses or apartments |
| Rooms | Rooms within homes |
| StorageLocations | Cupboards, shelves, drawers, boxes, and other locations |
| Categories | Inventory categories |
| CategoryAttributes | Configurable fields for each category |
| Items | General item definitions |
| ItemUnits | Individual physical instances |
| Photos | Photographs linked to items or units |
| Beds | Bed and sleeping-space records |
| Mattresses | Mattress dimensions and attributes |
| Tables | Table dimensions and shapes |
| Windows | Window dimensions and attributes |
| CompatibilityRules | Rules linking objects and textile categories |
| BeddingSets | Saved combinations |
| SetItems | Items or units belonging to a saved set |
| ItemHistory | History of item changes and movements |
| Invitations | User invitations |
| AuditLogs | Security and administrative activity |

### 16.1. Relationships

The database must support:

- One family group having multiple users.
- One family group having multiple homes.
- One home having multiple rooms.
- One room having multiple storage locations.
- Storage locations having nested child locations.
- One item having multiple physical units.
- One item or unit having multiple photographs.
- One bed, table, or window having multiple possible textile matches.
- One saved set containing multiple inventory items or units.

### 16.2. Data Integrity

The system must enforce:

- Valid relationships between records.
- Correct family group ownership.
- User access permissions.
- Valid category-specific attributes.
- Valid location references.
- Consistent dimensions and measurement units.
- Accurate links between saved sets and inventory items.

Deleting a record must not unintentionally destroy unrelated records or historical information.

Archiving should be preferred over permanent deletion where appropriate.

## 17. Technical Architecture Recommendations

The final technology stack should be selected by the development team based on scalability, maintainability, cost, and platform requirements.

The following architecture is recommended as a starting point.

### 17.1. Frontend

Potential technology:

- Flutter for iOS, Android, and Web.
- Alternatively, a dedicated web frontend alongside mobile applications.

The user interface must be responsive and adapted to mobile and desktop screens.

### 17.2. Backend

The backend should provide:

- User authentication.
- Family group management.
- Permission enforcement.
- Inventory management.
- Search and filtering.
- Storage location management.
- Compatibility calculations.
- AI service integration.
- Image management.
- Synchronization.
- Audit history.

A structured REST API or another well-documented API architecture may be used.

### 17.3. Database

Recommended:

- PostgreSQL.

Potential managed services:

- Supabase or another managed PostgreSQL platform.
- Alternatively, a custom backend and database infrastructure.

The database must support reliable relationships, indexing, filtering, and secure access.

### 17.4. Cloud Image Storage

Photographs should be stored in secure cloud object storage.

The database should store references and metadata rather than large image files.

The system should support image optimization and different image sizes for thumbnails and full-screen viewing.

### 17.5. AI Integration

The AI layer should support:

1. Image classification.
2. Color and pattern recognition.
3. Attribute suggestions.
4. Matching recommendations.
5. Natural-language search, if implemented.
6. Explanation of compatibility results.

AI functionality should be separated from the core inventory database so that AI providers can be changed without rebuilding the main application.

Technical compatibility calculations should be performed using explicit business rules and validated measurements.

AI should primarily assist with visual interpretation and recommendations.

### 17.6. Scalability

The system should be designed to support:

- Multiple family groups.
- Multiple homes per family group.
- Large inventories.
- Multiple photographs per item.
- Concurrent users.
- Additional categories.
- Additional matching relationships.
- Future languages and integrations.

## 18. Security and Privacy

The application will contain personal household information and photographs.

Security requirements include:

- Secure authentication.
- Encrypted connections.
- Secure password handling.
- Server-side authorization.
- Isolation of data between family groups.
- Secure image storage.
- Protection against unauthorized access.
- Audit logging for important actions.
- Secure account recovery.
- Controlled user invitations and revocation.

Users must only be able to access data belonging to family groups to which they have been granted access.

The application should comply with applicable data protection regulations, including GDPR where relevant.

## 19. Backup, Recovery, and Data Export

The system should provide:

- Automatic database backups.
- Recovery procedures.
- Protection against accidental deletion.
- Ability to archive items.
- Ability to restore archived records.
- Data export for inventory records.

A CSV or Excel export is recommended for inventory data.

An export should include relevant item attributes and storage locations.

Photographs may be exported separately or included in an archive, depending on implementation.

## 20. User Interface and User Experience

The interface should be:

- Simple and intuitive.
- Visually clear.
- Easy to use on mobile devices.
- Consistent across platforms.
- Designed for users who may not be technically experienced.

### 20.1. Item Cards

Inventory cards should display:

- Main photograph.
- Item name.
- Category.
- Dimensions.
- Main color.
- Quantity.
- Status.
- Storage location, shown as home / room / location name when those facts exist.

### 20.2. Item Details

An item detail screen should display all available information, including:

- Photograph gallery.
- Measurements.
- Attributes.
- Current location of each physical unit: home, room, containing storage, and location type.
- Status.
- Related objects and compatible textiles.
- History.
- Saved sets containing the item.

### 20.3. AI Matching Interface

The matching interface should allow the user to:

1. Select a bed, mattress, pillow, table, or window.
2. View compatible inventory items.
3. Compare suggested combinations.
4. Review technical compatibility.
5. Review visual compatibility.
6. See missing items.
7. Save a preferred combination.

The user must always be able to understand why a combination was recommended.

## 21. Recommended Development Priorities

The project should be developed in stages.

### Phase 1 — Core Inventory

- User registration and authentication.
- Family groups and user roles.
- Multiple homes.
- Rooms and storage locations.
- Textile categories.
- Manual item entry.
- Photographs.
- Item quantities and individual units.
- Item statuses.
- Search and filters.
- Cloud database and synchronization.

### Phase 2 — Household Objects and Matching Rules

- Beds.
- Mattresses.
- Tables.
- Windows.
- Category-specific measurements.
- Technical compatibility rules.
- Bed and bedding matching.
- Table and tablecloth matching.
- Window and curtain matching.
- Pillow and pillowcase matching.
- Mattress and sheet matching.

### Phase 3 — AI Features

- AI image recognition.
- Suggested item attributes.
- Color recognition.
- Pattern recognition.
- Visual compatibility assessment.
- Multiple combination recommendations.
- Explanations and missing-item detection.

### Phase 4 — Advanced Features

- Saved sets.
- QR codes for storage locations.
- Advanced history.
- Offline access.
- Notifications.
- Advanced reporting.
- Data export and recovery tools.
- Natural-language search.
- Additional configurable categories and relationships.

## 22. Acceptance Criteria

The initial application should not be considered complete until the following requirements have been verified.

### 22.1. Inventory

- Users can create, edit, and view inventory items.
- Each category displays the appropriate fields.
- Users can attach multiple photographs.
- Dimensions are stored consistently in centimeters.
- Items can be assigned to specific homes and storage locations.
- Individual physical units can have separate locations and statuses.
- Editing an item can change the location of each physical unit.
- A room or storage location that still contains items cannot be deleted.

### 22.2. Multi-User Access

- Multiple users can access the same family inventory.
- Administrators can invite and remove users.
- Roles are enforced correctly.
- Unauthorized users cannot access another family's data.

### 22.3. Search

- Users can search by category, dimensions, color, material, status, and location from the inventory.
- Multiple filters can be applied together, including house and a size such as 220 × 200.
- A size matches either orientation, within 1 cm on each side.
- An unreadable size is rejected and is not applied.
- Search results display the correct item and location information.

### 22.4. AI Recognition

- Users can add an item using a photograph.
- AI suggests a category and visible attributes.
- Users can correct all suggestions.
- Unknown measurements and materials are not fabricated.
- Items are not saved automatically without user confirmation.

### 22.5. Compatibility

- The system can identify compatible bedding for a selected bed or mattress.
- The system can match duvets with duvet covers.
- The system can match pillows with pillowcases and protectors.
- The system can match tables with tablecloths using shape and overhang.
- The system can match windows with curtains using curtain rail width, curtain length, fullness ratio, and attachment type.
- Technical compatibility is displayed separately from visual compatibility.
- The system can identify missing items.
- Users can save recommended combinations.
- A negative measurement is not saved and is not used as a size.
- A room chosen for a bed, mattress, table, or window belongs to the selected home.
- A QR code is shown only for a box.

### 22.6. Synchronization

- Changes made by one user become visible to other authorized users.
- Concurrent edits do not silently overwrite each other.
- Item movement and important changes are recorded in history.

## 23. Important Product Design Principles

The following principles must guide implementation.

#### 1. One shared inventory

All family members and devices must use the same cloud-based inventory.

#### 2. Flexible storage structure

Users must be able to create as many homes and nested storage locations as needed.

#### 3. Accurate item tracking

Individual physical items must be traceable when their locations, statuses, or attributes differ.

#### 4. Category-specific information

The application must display relevant fields for each category rather than using one generic form for everything.

#### 5. AI must not invent data

AI-generated suggestions must be distinguishable from verified information.

#### 6. Technical compatibility comes first

Dimensions, intended use, shape, and attachment requirements must be checked before visual matching.

#### 7. Visual matching is a separate assessment

Color and style recommendations must not override technical incompatibility.

#### 8. Flexible matching relationships

New relationships between household objects and textiles should be configurable without redesigning the application.

#### 9. User control

Users must be able to review, edit, and confirm AI suggestions and matching results.

#### 10. Future expansion

The application architecture should allow new textile categories, household objects, attributes, and matching rules to be added over time.

## 24. Final Project Definition

The final product should be a cross-platform, cloud-based household textile management application with shared family access, detailed inventory management, flexible storage tracking, AI-assisted image recognition, and intelligent textile matching.

Its key purpose is to help users answer three questions:

1. **What do I own?**
   - A complete and searchable inventory of household textiles and related objects.
2. **Where is it?**
   - Accurate information about which home, room, cupboard, shelf, drawer, or box contains each item.
3. **What can I use together?**
   - Intelligent recommendations that identify technically compatible and visually attractive combinations of bedding, tablecloths, curtains, and other household textiles.

The system must be built around a flexible data model and configurable compatibility rules so that it can grow beyond the initial categories without requiring a complete redesign.
