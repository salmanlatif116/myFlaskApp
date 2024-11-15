document.getElementById("scrapeForm").addEventListener("submit", async function (e) {
    e.preventDefault();

    const url = document.getElementById("url").value;
    const query = document.getElementById("query").value;
    const resultDiv = document.getElementById("result");

    const aboutContact = document.getElementById("aboutContact").checked;
    const includeDetail = document.getElementById("includeDetail").checked;

    resultDiv.innerHTML = "";

    if (url && aboutContact && includeDetail) {
        resultDiv.innerHTML = "Scraping emails from both sources, You'll get email once scraping done.";

        try {
            const [aboutContactResponse, includeDetailResponse] = await Promise.all([
                fetch("/api/v1/url/scrape-about-contact-and-send-emails/", {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                    },
                    body: JSON.stringify({ url }),
                }),
                fetch("/api/v1/url/scrape-all-and-send-emails/", {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                    },
                    body: JSON.stringify({ url }),
                })
            ]);

            if (!aboutContactResponse.ok || !includeDetailResponse.ok) {
                throw new Error("Failed to fetch data from one or both endpoints.");
            }

            const aboutContactData = await aboutContactResponse.json();
            const includeDetailData = await includeDetailResponse.json();

            // Combine results from both responses
            const combinedEmails = [
                ...(aboutContactData.Emails || []),
                ...(includeDetailData.Emails || [])
            ];

            resultDiv.innerHTML = combinedEmails.length > 0
                ? `<h3>Emails Found:</h3><ul>${combinedEmails.map(email => `<li style="list-style-type: none;">${email}</li>`).join("")}</ul>`
                : "<p>No emails found on this URL from both sources.</p>";
        } catch (error) {
            resultDiv.innerHTML = `<p>Error: ${error.message}</p>`;
        }
    } else if (url && aboutContact) {
        // Existing aboutContact fetch logic
        resultDiv.innerHTML = "Scraping about & contact emails, You'll get email once scraping done.";

        try {
            const response = await fetch("/api/v1/url/scrape-about-contact-and-send-emails/", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({ url }),
            });

            if (!response.ok) throw new Error("Failed to fetch data.");

            const data = await response.json();
            resultDiv.innerHTML = data.Emails && data.Emails.length > 0
                ? `<h3>Emails Found:</h3><ul>${data.Emails.map(email => `<li style="list-style-type: none;">${email}</li>`).join("")}</ul>`
                : "<p>No emails found on this URL.</p>";
        } catch (error) {
            resultDiv.innerHTML = `<p>Error: ${error.message}</p>`;
        }
    } else if (url && includeDetail) {
        // Existing includeDetail fetch logic
        resultDiv.innerHTML = "Scraping detail emails, You'll get email once scraping done.";

        try {
            const response = await fetch("/api/v1/url/scrape-all-and-send-emails/", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({ url }),
            });

            if (!response.ok) throw new Error("Failed to fetch data.");

            const data = await response.json();
            resultDiv.innerHTML = data.Emails && data.Emails.length > 0
                ? `<h3>Emails Found:</h3><ul>${data.Emails.map(email => `<li style="list-style-type: none;">${email}</li>`).join("")}</ul>`
                : "<p>No emails found on this URL.</p>";
        } catch (error) {
            resultDiv.innerHTML = `<p>Error: ${error.message}</p>`;
        }
    } else if (query) {
        // Existing query fetch logic
        resultDiv.innerHTML = "Scraping URLs, You'll get email once scraping done.";

        try {
            const response = await fetch("/api/v1/scrape/google-map/", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({ query }),
            });

            if (!response.ok) throw new Error("Failed to fetch data.");

            const data = await response.json();
            resultDiv.innerHTML = data.Emails && data.Emails.length > 0
                ? `<h3>Emails Found:</h3><ul>${data.Emails.map(email => `<li style="list-style-type: none;">${email}</li>`).join("")}</ul>`
                : "<p>No emails found on this Query.</p>";
        } catch (error) {
            resultDiv.innerHTML = `<p>Error: ${error.message}</p>`;
        }
    } else {
        resultDiv.innerHTML = "<p>Please enter either a URL or a query or select any checkbox.</p>";
    }
});
