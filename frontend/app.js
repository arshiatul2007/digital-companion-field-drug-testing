let capturedImage = null;
let currentLocation = null;

const camera = document.getElementById("camera");
const canvas = document.getElementById("canvas");
const imageInput = document.getElementById("imageInput");


// START CAMERA
document.getElementById("startCamera").addEventListener("click", async () => {

    try {
        const stream = await navigator.mediaDevices.getUserMedia({
            video: true
        });

        camera.srcObject = stream;

    } catch (error) {
        alert("Could not access camera.");
        console.error(error);
    }
});


// CAPTURE IMAGE
document.getElementById("capture").addEventListener("click", () => {

    if (!camera.srcObject) {
        alert("Please start the camera first.");
        return;
    }

    canvas.width = camera.videoWidth;
    canvas.height = camera.videoHeight;

    const context = canvas.getContext("2d");

    context.drawImage(
        camera,
        0,
        0,
        canvas.width,
        canvas.height
    );

    canvas.toBlob((blob) => {
        capturedImage = blob;
        alert("Image captured successfully.");
    }, "image/jpeg");
});


// SELECT IMAGE FROM COMPUTER
imageInput.addEventListener("change", (event) => {

    const file = event.target.files[0];

    if (file) {
        capturedImage = file;
        alert("Image selected successfully.");
    }
});


// GET GPS LOCATION
document.getElementById("getLocation").addEventListener("click", () => {

    if (!navigator.geolocation) {
        alert("Geolocation is not supported by this browser.");
        return;
    }

    document.getElementById("locationStatus").textContent =
        "Getting location...";

    navigator.geolocation.getCurrentPosition(

        (position) => {

            currentLocation = {
                latitude: position.coords.latitude,
                longitude: position.coords.longitude,
                accuracy: position.coords.accuracy
            };

            document.getElementById("locationStatus").textContent =
                "Location captured successfully.";

        },

        (error) => {

            document.getElementById("locationStatus").textContent =
                "Could not get location.";

            console.error(error);
        }
    );
});


// CREATE TEST RECORD
document.getElementById("submitTest").addEventListener("click", async () => {

    const operatorId =
        document.getElementById("operatorId").value.trim();

    if (!operatorId) {
        alert("Please enter Operator ID.");
        return;
    }

    if (!capturedImage) {
        alert("Please capture or select an image.");
        return;
    }

    const formData = new FormData();

    formData.append("image", capturedImage);
    formData.append("operator_id", operatorId);

    if (currentLocation) {

        formData.append(
            "latitude",
            currentLocation.latitude
        );

        formData.append(
            "longitude",
            currentLocation.longitude
        );

        formData.append(
            "gps_accuracy",
            currentLocation.accuracy
        );
    }

    try {

        const response = await fetch(
            "/api/tests",
            {
                method: "POST",
                body: formData
            }
        );

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || "Test failed");
        }

        document.getElementById("result").innerHTML = `
            <div class="test-item">
                <h3>Test Created Successfully</h3>

                <p><strong>Test ID:</strong> ${data.id}</p>

                <p><strong>Result:</strong> ${data.result}</p>

                <p><strong>Confidence:</strong> ${data.confidence}</p>

                <p><strong>Image Hash:</strong> ${data.image_hash}</p>

                <p><strong>Record Hash:</strong> ${data.record_hash}</p>
            </div>
        `;

        loadTests();

    } catch (error) {

        alert(error.message);
        console.error(error);
    }
});


// LOAD TEST LOG
async function loadTests(search = "") {

    try {

        const response = await fetch(
            "/api/tests?search=" +
            encodeURIComponent(search)
        );

        const tests = await response.json();

        const log = document.getElementById("testLog");

        log.innerHTML = "";

        if (tests.length === 0) {

            log.innerHTML = "<p>No test records found.</p>";
            return;
        }

        tests.forEach((test) => {

            const div = document.createElement("div");

            div.className = "test-item";

            div.innerHTML = `
                <p><strong>Test ID:</strong> ${test.id}</p>
                <p><strong>Operator:</strong> ${test.operator_id}</p>
                <p><strong>Result:</strong> ${test.result}</p>
                <p><strong>Time:</strong> ${test.timestamp}</p>
            `;

            log.appendChild(div);
        });

    } catch (error) {

        console.error(error);
    }
}


// SEARCH TEST LOG
document.getElementById("searchButton").addEventListener("click", () => {

    const search =
        document.getElementById("search").value.trim();

    loadTests(search);
});


// VERIFY RECORD
document.getElementById("verifyButton").addEventListener("click", async () => {

    const testId =
        document.getElementById("verifyId").value.trim();

    if (!testId) {
        alert("Please enter a Test ID.");
        return;
    }

    try {

        const response = await fetch(
            `/api/tests/${testId}/verify`
        );

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || "Verification failed");
        }

        document.getElementById("verification").innerHTML = `
            <div class="test-item">

                <h3>
                    ${data.verified ? "✅ VERIFIED" : "❌ NOT VERIFIED"}
                </h3>

                <p>
                    Image Hash:
                    ${data.image_hash_valid ? "✅ Valid" : "❌ Invalid"}
                </p>

                <p>
                    Record Hash:
                    ${data.record_hash_valid ? "✅ Valid" : "❌ Invalid"}
                </p>

                <p>
                    Digital Signature:
                    ${data.signature_valid ? "✅ Valid" : "❌ Invalid"}
                </p>

            </div>
        `;

    } catch (error) {

        alert(error.message);
        console.error(error);
    }
});


// LOAD RECORDS WHEN PAGE OPENS
loadTests();