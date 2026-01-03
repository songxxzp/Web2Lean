/**
 * Math rendering utilities using KaTeX
 */
import katex from 'katex'

/**
 * Convert LaTeX math expressions to HTML
 * Handles both inline ($...$) and display ($$...$$) math
 *
 * @param {string} text - Text containing LaTeX expressions
 * @returns {string} HTML with rendered math
 */
export function renderMath(text) {
  if (!text || typeof text !== 'string') {
    return text
  }

  // Process display math first ($$...$$) to avoid conflicts with inline math
  let result = text.replace(/\$\$([\s\S]+?)\$\$/g, (match, math) => {
    try {
      return katex.renderToString(math.trim(), {
        displayMode: true,
        throwOnError: false,
        trust: true
      })
    } catch (e) {
      console.error('KaTeX display mode error:', e)
      return match
    }
  })

  // Process inline math ($...$)
  result = result.replace(/\$([^\$]+?)\$/g, (match, math) => {
    try {
      return katex.renderToString(math.trim(), {
        displayMode: false,
        throwOnError: false,
        trust: true
      })
    } catch (e) {
      console.error('KaTeX inline error:', e)
      return match
    }
  })

  return result
}

/**
 * Convert plain text to HTML with line breaks and math rendering
 *
 * @param {string} text - Plain text content
 * @returns {string} HTML with line breaks and rendered math
 */
export function renderContent(text) {
  if (!text || typeof text !== 'string') {
    return ''
  }

  // First render math
  const withMath = renderMath(text)

  // Convert line breaks to <br>
  return withMath.replace(/\n/g, '<br>')
}
