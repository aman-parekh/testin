# CLAUDE.md
> Automatically loaded by Claude Code as its system context.
> Every change made in this repo MUST follow these rules.

---

## 1. Project Overview

This is a **Kotlin + Jetpack Compose** Android application.
All UI must follow the gradient design system below — no exceptions.

---

## 2. Gradient Design System ← MANDATORY

Every composable you create or modify MUST use `Brush` gradients.
Flat solid-colour backgrounds and buttons are **forbidden**.

### Colour Tokens

| Token      | Start                 | End                   |
|------------|-----------------------|-----------------------|
| Primary    | `Color(0xFF6366F1)`   | `Color(0xFF8B5CF6)`   |
| Accent     | `Color(0xFF06B6D4)`   | `Color(0xFF3B82F6)`   |
| Success    | `Color(0xFF10B981)`   | `Color(0xFF059669)`   |
| Warning    | `Color(0xFFF59E0B)`   | `Color(0xFFD97706)`   |
| Error      | `Color(0xFFEF4444)`   | `Color(0xFFDC2626)`   |
| Background | `Color(0xFF0F0C29)`   | `Color(0xFF24243E)`   |

### Code Patterns

```kotlin
// ✅ Screen background
Box(
    modifier = Modifier.fillMaxSize().background(
        Brush.verticalGradient(
            listOf(Color(0xFF0F0C29), Color(0xFF302B63), Color(0xFF24243E))
        )
    )
)

// ✅ Primary button — never use solid containerColor
Box(
    modifier = Modifier
        .background(
            Brush.linearGradient(listOf(Color(0xFF6366F1), Color(0xFF8B5CF6))),
            RoundedCornerShape(12.dp)
        )
        .clickable(onClick = onClick)
        .padding(horizontal = 24.dp, vertical = 14.dp)
) {
    Text(label, color = Color.White, fontWeight = FontWeight.SemiBold)
}

// ✅ Card with subtle gradient
Surface(
    modifier = Modifier
        .fillMaxWidth()
        .background(
            Brush.linearGradient(
                listOf(Color(0xFF6366F1).copy(alpha = 0.10f), Color(0xFF8B5CF6).copy(alpha = 0.10f))
            ),
            RoundedCornerShape(16.dp)
        )
)
```

**Rules:**
- Text on gradient → always `Color.White` or `Color.White.copy(alpha = 0.87f)`
- Icons on gradient → `tint = Color.White`
- Transitions → use `animateColorAsState` / `animateFloatAsState`

---

## 3. Architecture

```
ui/<feature>/
  <Feature>Screen.kt       ← stateless composable, receives UiState + callbacks
  <Feature>ViewModel.kt    ← @HiltViewModel, exposes StateFlow<UiState>
  <Feature>UiState.kt      ← sealed class or data class

domain/model/              ← pure Kotlin data models
domain/repository/         ← interfaces only
domain/usecase/            ← single-responsibility use cases

data/repository/           ← @Singleton implementations
data/remote/               ← Retrofit interfaces
data/local/                ← Room DAOs
```

**Rules:**
- ViewModels must NOT import `android.view.*` or hold `Context`
- Repositories are the only layer that calls network or database
- Use `collectAsStateWithLifecycle()` in Compose (not `collectAsState()`)
- No `!!` operators — use `?.let {}` or `requireNotNull(x) { "message" }`

---

## 4. Testing Requirements

Every PR touching business logic MUST include tests:

| Layer      | Framework             | Required cases                         |
|------------|-----------------------|----------------------------------------|
| ViewModel  | JUnit 4 + Turbine     | Happy path, error state, loading state |
| Repository | JUnit 4 + Mockito     | Success, network failure, cache hit    |

---

## 5. Accessibility

- Every `Image` and `Icon` needs a non-empty `contentDescription`
- Minimum touch target: 48×48 dp

---

## 6. Git & PR Conventions

- Branch: `claude/fix-issue-{N}-description` or `claude/feat-issue-{N}-description`
- Commit: `fix: description (#N)` or `feat: description (#N)`
- PR title must match commit format
- No hardcoded strings → use `strings.xml`
