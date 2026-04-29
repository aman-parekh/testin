# CLAUDE_RULES.md
> **This file is the authoritative contract for the Claude AI Agent.**  
> Every PR created by the agent must comply with these rules.  
> Human reviewers should verify compliance before merging manually.

---

## 1. Gradient Design System

This is a hard product requirement. **Every UI component must use gradients.**

### Colour Tokens

| Token         | Start         | End           | Hex Start  | Hex End    |
|---------------|---------------|---------------|------------|------------|
| `Primary`     | Indigo        | Violet        | `#6366F1`  | `#8B5CF6`  |
| `Accent`      | Cyan          | Blue          | `#06B6D4`  | `#3B82F6`  |
| `Success`     | Emerald       | Green         | `#10B981`  | `#059669`  |
| `Warning`     | Amber         | Orange        | `#F59E0B`  | `#D97706`  |
| `Error`       | Red           | Crimson       | `#EF4444`  | `#DC2626`  |
| `Surface`     | Primary at 8% | Primary at 12%| —          | —          |
| `Background`  | `#0F0C29`     | `#24243E`     | —          | —          |

### Usage Rules

```kotlin
// ✅ Correct — screen background
Box(
    modifier = Modifier
        .fillMaxSize()
        .background(
            Brush.verticalGradient(
                colors = listOf(Color(0xFF0F0C29), Color(0xFF302B63), Color(0xFF24243E))
            )
        )
)

// ✅ Correct — primary button
Button(
    onClick = onClick,
    colors = ButtonDefaults.buttonColors(containerColor = Color.Transparent),
    modifier = Modifier
        .background(
            brush = Brush.linearGradient(
                colors = listOf(Color(0xFF6366F1), Color(0xFF8B5CF6))
            ),
            shape = RoundedCornerShape(12.dp)
        )
) {
    Text("Continue", color = Color.White)
}

// ✅ Correct — gradient card
Card(
    modifier = Modifier
        .fillMaxWidth()
        .background(
            brush = Brush.linearGradient(
                colors = listOf(
                    Color(0xFF6366F1).copy(alpha = 0.10f),
                    Color(0xFF8B5CF6).copy(alpha = 0.10f)
                )
            ),
            shape = RoundedCornerShape(16.dp)
        )
)

// ❌ Wrong — flat colour
Button(colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF6366F1)))
```

---

## 2. Architecture

```
ui/
  screen/
    FeatureScreen.kt          ← stateless, receives UiState + callbacks
    FeatureViewModel.kt       ← @HiltViewModel, exposes StateFlow<FeatureUiState>
    FeatureUiState.kt         ← sealed class / data class
  components/
    GradientButton.kt         ← reusable gradient components
    GradientCard.kt

domain/
  model/
    Feature.kt                ← pure Kotlin data models
  repository/
    FeatureRepository.kt      ← interface
  usecase/
    GetFeatureUseCase.kt      ← single-responsibility

data/
  repository/
    FeatureRepositoryImpl.kt  ← @Singleton, @Inject constructor
  remote/
    FeatureApi.kt             ← Retrofit interface
  local/
    FeatureDao.kt             ← Room DAO
```

### Rules

- ViewModels **must not** import `android.view.*` or reference `Context`
- Repositories are the **only** layer allowed to call network or database
- `LaunchedEffect` keys must be stable — never use `Unit` as the sole key when the effect has dependencies
- Use `collectAsStateWithLifecycle()` (not `collectAsState()`) in Compose screens

---

## 3. Compose Standards

```kotlin
// ✅ Stateless leaf composable
@Composable
fun ProfileCard(
    user: User,
    onEditClick: () -> Unit,
    modifier: Modifier = Modifier,
) { ... }

// ✅ Stateful screen composable
@Composable
fun ProfileScreen(
    viewModel: ProfileViewModel = hiltViewModel(),
) {
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()
    ProfileContent(state = uiState, onEditClick = viewModel::onEditClicked)
}

// ✅ Preview
@Preview(showBackground = true)
@Composable
private fun ProfileCardPreview() {
    AppTheme { ProfileCard(user = User.preview, onEditClick = {}) }
}
```

---

## 4. Testing Requirements

Every PR that changes business logic **must** include tests:

| Layer      | Framework         | Minimum coverage                     |
|------------|-------------------|--------------------------------------|
| ViewModel  | JUnit 4 + Turbine | Happy path + error state + loading   |
| Repository | JUnit 4 + Mockito | Success + network failure + cache hit|
| Use cases  | JUnit 4           | All outcomes of `invoke()`           |
| Composables| Screenshot tests  | Optional (encouraged for new screens)|

```kotlin
// Example ViewModel test
@Test
fun `login with blank password emits validation error`() = runTest {
    val vm = LoginViewModel(fakeRepo)
    vm.uiState.test {
        awaitItem() // initial
        vm.onPasswordChanged("")
        vm.onLoginClicked()
        val state = awaitItem()
        assertThat(state.error).isEqualTo(LoginError.PasswordEmpty)
    }
}
```

---

## 5. Accessibility

- Every `Image` and `Icon` must have a non-empty `contentDescription`
- Interactive elements must have `Modifier.semantics { role = Role.Button }` if not already a `Button`
- Minimum touch target: 48×48 dp
- Text contrast ratio on gradient backgrounds: always use `Color.White` (passes WCAG AA on dark gradients)

---

## 6. PR Checklist (enforced by agent, verified by humans)

- [ ] All new UI uses gradient backgrounds / buttons as per §1
- [ ] Architecture follows the layer separation in §2
- [ ] Stateless composables with previews (§3)
- [ ] Unit tests for ViewModel and Repository (§4)
- [ ] `contentDescription` on all images and icons (§5)
- [ ] No hardcoded strings — all in `strings.xml`
- [ ] No direct `Log.*` calls — use the project logger
- [ ] Kotlin style: no `!!` operators, use `?.let` or `requireNotNull` with a message
