// Newspaper Archive Scraper with Debug Information
// This script uses multiple selector strategies to find article content

// Function to extract the newspaper metadata
function extractNewspaperMetadata() {
    // Extract information from the page title
    const pageTitle = document.querySelector('h1').textContent;
    const match = pageTitle.match(/Neue Zürcher Zeitung, Number (\d+), (\d+) (\w+) (\d+)/);
    
    if (!match) return null;
    
    const issueNumber = parseInt(match[1]);
    const day = parseInt(match[2]);
    const month = match[3];
    const year = parseInt(match[4]);
    
    // Convert month name to month number (assuming German month names)
    const monthMap = {
      'Januar': '01', 'Februar': '02', 'März': '03', 'April': '04',
      'Mai': '05', 'Juni': '06', 'Juli': '07', 'August': '08',
      'September': '09', 'Oktober': '10', 'November': '11', 'Dezember': '12'
    };
    
    const monthNum = monthMap[month] || '01';
    const dateStr = `${year}-${monthNum}-${day.toString().padStart(2, '0')}`;
    
    // Try to determine day of week from metadata if available, otherwise use Monday as default
    const dayOfWeek = "Montag"; // Default
    
    // Default to 4 pages or try to determine from page navigation
    const pages = 4;
    
    return {
      newspaper: "Neue Zürcher Zeitung",
      issue_number: issueNumber,
      date: dateStr,
      day_of_week: dayOfWeek,
      pages: pages
    };
  }
  
  // Function to extract the current article using multiple selector strategies
  function extractCurrentArticle() {
    console.log("Attempting to extract current article...");
    
    // STRATEGY 1: Try to find the title using various selector patterns
    let titleElement = null;
    
    // Try selector patterns in order of specificity
    const titleSelectors = [
      'div.documentdisplayleftpanesectiontextheader p[dir="auto"]',
      '#documentdisplayleftpanesectiontextcontainer p[dir="auto"]:first-of-type',
      'p[dir="auto"]:first-of-type',
      '.documentdisplayleftpanesectiontextheader p',
      '#sectionleveltabtextareacontent p[dir="auto"]:first-of-type'
    ];
    
    for (const selector of titleSelectors) {
      titleElement = document.querySelector(selector);
      if (titleElement) {
        console.log(`Found title element using selector: ${selector}`);
        break;
      }
    }
    
    // If still not found, try a more aggressive approach
    if (!titleElement) {
      console.log("Title element not found with standard selectors, trying all paragraphs...");
      
      // Get all paragraphs in the document
      const allParagraphs = document.querySelectorAll('p');
      
      // Look for paragraphs that appear to be titles (short, ends with period)
      for (const para of allParagraphs) {
        const text = para.textContent.trim();
        // Exclude UI elements and find likely titles
        if (text.length > 0 && text.length < 100 && 
            !text.includes("Why may this text contain mistakes?") && 
            !text.includes("Correct this text")) {
          titleElement = para;
          console.log("Found potential title element from scanning all paragraphs");
          break;
        }
      }
    }
    
    // DEBUGGING: Log element details
    if (!titleElement) {
      console.log("STILL UNABLE TO FIND TITLE ELEMENT - DEBUGGING INFO:");
      
      // Log all paragraph elements to help diagnose
      console.log("All paragraph elements on page:");
      document.querySelectorAll('p').forEach((p, index) => {
        console.log(`Paragraph ${index}:`, p.textContent.trim().substring(0, 50) + '...');
      });
      
      // Log key container elements
      console.log("Text container:", document.querySelector('#documentdisplayleftpanesectiontextcontainer'));
      console.log("Text header:", document.querySelector('.documentdisplayleftpanesectiontextheader'));
      
      return null;
    }
    
    // Extract the title text
    const title = titleElement.textContent.trim();
    console.log(`Extracted title: "${title}"`);
    
    // STRATEGY 2: Get the body text
    let bodyText = "";
    
    // First try to get paragraphs after the title element
    let nextElement = titleElement.nextElementSibling;
    while (nextElement) {
      if (nextElement.tagName === 'P') {
        const paraText = nextElement.textContent.trim();
        if (!paraText.includes("Why may this text contain mistakes?") && 
            !paraText.includes("Correct this text")) {
          bodyText += paraText + " ";
        }
      }
      nextElement = nextElement.nextElementSibling;
    }
    
    // If that didn't work, try to get all paragraphs in the container except the first one
    if (bodyText.trim() === "") {
      console.log("No body text found after title, trying container paragraphs...");
      
      const container = document.querySelector('#documentdisplayleftpanesectiontextcontainer');
      if (container) {
        // Get all paragraphs except the one that matches the title
        const paragraphs = container.querySelectorAll('p');
        let foundTitle = false;
        
        for (const para of paragraphs) {
          const paraText = para.textContent.trim();
          
          // Skip UI elements
          if (paraText.includes("Why may this text contain mistakes?") || 
              paraText.includes("Correct this text")) {
            continue;
          }
          
          // Skip the title paragraph
          if (!foundTitle && paraText === title) {
            foundTitle = true;
            continue;
          }
          
          // Add the paragraph to the body
          bodyText += paraText + " ";
        }
      }
    }
    
    // If still no body text, try to get all text from the container and remove the title
    if (bodyText.trim() === "") {
      console.log("Still no body text, trying to extract from container text...");
      
      const container = document.querySelector('#documentdisplayleftpanesectiontextcontainer');
      if (container) {
        let fullText = container.textContent;
        
        // Remove UI text
        fullText = fullText.replace("Why may this text contain mistakes?", "");
        fullText = fullText.replace("Correct this text", "");
        
        // Remove the title if it's in the text
        if (fullText.includes(title)) {
          fullText = fullText.substring(fullText.indexOf(title) + title.length);
        }
        
        bodyText = fullText.trim();
      }
    }
    
    // Clean up the body text (remove extra whitespace)
    bodyText = bodyText.replace(/\s+/g, ' ').trim();
    console.log(`Extracted body text (first 100 chars): "${bodyText.substring(0, 100)}..."`);
    
    // Return the article
    return {
      title: title,
      body: bodyText
    };
  }
  
  // Function to check if an article exists in the collection
  function articleExists(collection, title) {
    return collection.some(article => article.title === title);
  }
  
  // Main function to set up the collector
  function setupArticleCollector() {
    // Get newspaper metadata
    const metadata = extractNewspaperMetadata();
    console.log("Metadata extracted:", metadata);
    
    // Initialize articles array
    const articles = [];
    
    // Try to extract the currently visible article
    const currentArticle = extractCurrentArticle();
    if (currentArticle && currentArticle.title) {
      articles.push(currentArticle);
      console.log(`Initial article captured: "${currentArticle.title}"`);
    }
    
    // Function to display all elements with text content
    window.debugTextElements = function() {
      console.log("=== ALL TEXT ELEMENTS ===");
      document.querySelectorAll('*').forEach(el => {
        if (el.childNodes.length === 1 && el.childNodes[0].nodeType === 3 && el.textContent.trim()) {
          console.log(`${el.tagName}${el.id ? '#'+el.id : ''}${Array.from(el.classList).map(c => '.'+c).join('')}: "${el.textContent.trim().substring(0, 50)}..."`);
        }
      });
      console.log("========================");
    };
    
    // Create a function to manually extract text from element by ID or selector
    window.extractFromElement = function(selector) {
      const el = document.querySelector(selector);
      if (el) {
        console.log(`Element found: ${selector}`);
        console.log(`Text content: "${el.textContent.trim()}"`);
        return el.textContent.trim();
      } else {
        console.log(`Element not found: ${selector}`);
        return null;
      }
    };
    
    // Create a function to add new articles to the collection
    window.captureCurrentArticle = function() {
      const article = extractCurrentArticle();
      
      if (article && article.title) {
        // Check if we already have this article
        if (!articleExists(articles, article.title)) {
          articles.push(article);
          console.log(`Article captured: "${article.title}"`);
          console.log(`Total articles: ${articles.length}`);
          return `Captured: ${article.title}`;
        } else {
          return `Article "${article.title}" already captured`;
        }
      } else {
        return "No article found or unable to extract";
      }
    };
    
    // Create a function to get all articles as JSON
    window.generateNewspaperJSON = function() {
      // One last attempt to capture the current article
      window.captureCurrentArticle();
      
      const result = {
        ...metadata,
        articles: articles
      };
      
      const jsonString = JSON.stringify(result, null, 2);
      console.log(jsonString);
      
      // Create a way to download the JSON
      const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(jsonString);
      const downloadAnchorNode = document.createElement('a');
      downloadAnchorNode.setAttribute("href", dataStr);
      downloadAnchorNode.setAttribute("download", "newspaper_articles.json");
      document.body.appendChild(downloadAnchorNode);
      downloadAnchorNode.click();
      downloadAnchorNode.remove();
      
      return jsonString;
    };
    
    // Function to manually add an article
    window.addArticleManually = function(title, body) {
      if (title && body) {
        if (!articleExists(articles, title)) {
          articles.push({ title, body });
          console.log(`Article manually added: "${title}"`);
          console.log(`Total articles: ${articles.length}`);
          return `Added: ${title}`;
        } else {
          return `Article "${title}" already exists`;
        }
      } else {
        return "Both title and body are required";
      }
    };
    
    console.log("======= NEWSPAPER SCRAPER INSTRUCTIONS =======");
    console.log("1. Navigate to each article you want to capture");
    console.log("2. For each article, run window.captureCurrentArticle()");
    console.log("3. If automatic capture fails, you can:");
    console.log("   - Run window.debugTextElements() to see all text elements");
    console.log("   - Add articles manually with window.addArticleManually(title, body)");
    console.log("4. When finished, run window.generateNewspaperJSON() to get the JSON and download the file");
    console.log("=============================================");
  }
  
  // Start the article collector
  setupArticleCollector();