import XCTest

@MainActor
final class AlertTapTests: XCTestCase {
    func testRealTapsDuringOccupiedMainDispatchBlock() {
        continueAfterFailure = false
        let app = XCUIApplication()
        app.launch()
        let download = app.buttons["Download"]
        XCTAssertTrue(download.waitForExistence(timeout: 15))
        XCTAssertTrue(download.isHittable)
        download.tap()
        if ProcessInfo.processInfo.environment["TOUCHHLE_BASELINE_EXPECTED"] == "1" {
            XCTAssertTrue(download.waitForNonExistence(timeout: 10), "A real external tap must dismiss the old visual alert")
            XCTAssertTrue(app.staticTexts["Baseline pending"].waitForExistence(timeout: 35))
            return
        }
        XCTAssertTrue(app.staticTexts["Download delivered"].waitForExistence(timeout: 10))
        app.buttons["Game touch"].tap()
        let cancel = app.buttons["Cancel"]
        XCTAssertTrue(cancel.waitForExistence(timeout: 10))
        cancel.tap()
        XCTAssertTrue(app.staticTexts["Cancel delivered"].waitForExistence(timeout: 10))
        app.buttons["Game touch"].tap()
        XCTAssertTrue(app.staticTexts["All native taps passed"].waitForExistence(timeout: 10))
    }
}
