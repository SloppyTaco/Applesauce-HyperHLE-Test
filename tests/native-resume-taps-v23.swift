import XCTest

@MainActor
final class ResumeTapTests: XCTestCase {
    func testNativeInterruptionsAndQueueAvailability() {
        continueAfterFailure = false
        let app = XCUIApplication()
        let baseline = ProcessInfo.processInfo.environment["RESUME_BASELINE_EXPECTED"] == "1"
        app.launchEnvironment["RESUME_BASELINE"] = baseline ? "1" : "0"
        XCUIDevice.shared.orientation = .landscapeLeft
        app.launch()
        XCTAssertTrue(app.staticTexts["Ready to start"].waitForExistence(timeout: 15))
        let start = app.buttons["resume-start"]
        XCTAssertTrue(start.isHittable)
        start.tap()
        if baseline {
            XCTAssertTrue(app.staticTexts["Baseline queue blocked"].waitForExistence(timeout: 15))
            XCTAssertFalse(app.staticTexts["Baseline not reproduced"].exists)
            return
        }
        XCTAssertTrue(app.staticTexts["Core ready"].waitForExistence(timeout: 15))
        let game = app.buttons["resume-game-touch"]
        XCTAssertTrue(game.isHittable)
        game.tap()
        XCTAssertTrue(app.staticTexts["Tap 1"].waitForExistence(timeout: 5))

        XCUIDevice.shared.press(.home)
        app.activate()
        XCTAssertTrue(app.staticTexts["Foreground 1"].waitForExistence(timeout: 10))
        XCTAssertTrue(game.isHittable)
        game.tap()
        XCTAssertTrue(app.staticTexts["Tap 2"].waitForExistence(timeout: 5))

        // Open and dismiss the system Control Center with actual edge gestures.
        let top = app.coordinate(withNormalizedOffset: CGVector(dx: 0.96, dy: 0.01))
        let bottom = app.coordinate(withNormalizedOffset: CGVector(dx: 0.96, dy: 0.85))
        top.press(forDuration: 0.05, thenDragTo: bottom)
        let springboard = XCUIApplication(bundleIdentifier: "com.apple.springboard")
        // A fresh iOS 26 simulator can have an empty controls page. Verify the
        // actual panel root and its observed system toolbar, not a user widget.
        let panel = springboard.otherElements["cc-root-folder-view"]
        XCTAssertTrue(panel.waitForExistence(timeout: 8), springboard.debugDescription)
        XCTAssertTrue(springboard.buttons["Add Controls"].exists)
        // The target app's accessibility hit-test flag can stay true beneath
        // system UI. Require the real UIKit inactive state, without disabling
        // or replacing any game input in the fixture.
        XCTAssertTrue(app.staticTexts["Native inactive 2"].waitForExistence(timeout: 8), app.debugDescription)
        let closeStart = springboard.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.98))
        let closeEnd = springboard.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.12))
        closeStart.press(forDuration: 0.05, thenDragTo: closeEnd)
        XCTAssertTrue(app.staticTexts["Foreground 2"].waitForExistence(timeout: 10), app.debugDescription)
        XCTAssertTrue(game.isHittable, app.debugDescription)
        game.tap()
        XCTAssertTrue(app.staticTexts["Tap 3"].waitForExistence(timeout: 5))

        XCUIDevice.shared.press(.home)
        app.activate()
        XCTAssertTrue(app.staticTexts["Foreground 3"].waitForExistence(timeout: 10))
        XCTAssertTrue(game.isHittable)
        game.tap()
        XCTAssertTrue(app.staticTexts["Tap 4"].waitForExistence(timeout: 5))
        let exit = app.buttons["resume-exit"]
        XCTAssertTrue(exit.isHittable)
        exit.tap()
        XCTAssertTrue(app.staticTexts["All resume taps passed"].waitForExistence(timeout: 10))
        XCTAssertFalse(app.staticTexts["Resume checks failed"].exists)
    }
}
