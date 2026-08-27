const LESSON_ROW_SELECTOR = 'button[data-testid="lesson-row"]'

function orderedLessonRows() {
  return [...document.querySelectorAll(LESSON_ROW_SELECTOR)].sort(
    (a, b) => Number(a.dataset.lessonOrder || 0) - Number(b.dataset.lessonOrder || 0),
  )
}

function currentLessonOrder() {
  const label = [...document.querySelectorAll('main p')].find((element) =>
    /^Aula\s+\d+$/i.test((element.textContent || '').trim()),
  )
  if (!label) return null
  const match = (label.textContent || '').match(/Aula\s+(\d+)/i)
  return match ? Number(match[1]) : null
}

function nextLessonButton() {
  return [...document.querySelectorAll('button')].find(
    (button) => (button.textContent || '').trim() === 'Próxima aula',
  )
}

function syncLessonSequenceLocks() {
  const rows = orderedLessonRows()
  if (!rows.length) return

  rows.forEach((row, index) => {
    const previous = index > 0 ? rows[index - 1] : null
    const locked = Boolean(previous && previous.dataset.lessonCompleted !== 'true')

    row.dataset.lessonLocked = locked ? 'true' : 'false'
    row.disabled = locked
    row.setAttribute('aria-disabled', locked ? 'true' : 'false')

    if (locked) {
      row.title = `Conclua a aula ${previous.dataset.lessonOrder} antes de avançar.`
    } else {
      row.removeAttribute('title')
    }
  })

  const nextButton = nextLessonButton()
  if (!nextButton) return

  const order = currentLessonOrder()
  const current = rows.find((row) => Number(row.dataset.lessonOrder) === order)
  const currentIndex = current ? rows.indexOf(current) : -1
  const next = currentIndex >= 0 ? rows[currentIndex + 1] : null
  const locked = Boolean(next && current?.dataset.lessonCompleted !== 'true')

  nextButton.dataset.lessonNextLocked = locked ? 'true' : 'false'
  nextButton.disabled = locked
  nextButton.setAttribute('aria-disabled', locked ? 'true' : 'false')

  if (locked) {
    nextButton.title = 'Finalize esta aula antes de avançar para a próxima.'
  } else {
    nextButton.removeAttribute('title')
  }
}

export function installLessonSequenceGuard() {
  if (typeof document === 'undefined' || typeof MutationObserver === 'undefined') return

  const observer = new MutationObserver(() => syncLessonSequenceLocks())
  observer.observe(document.body, {
    childList: true,
    subtree: true,
    attributes: true,
    attributeFilter: ['data-lesson-completed', 'data-lesson-order'],
  })

  syncLessonSequenceLocks()
}
