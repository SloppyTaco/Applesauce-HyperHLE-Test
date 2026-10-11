/* Test-only UIKit harness. Contains no game executable/assets. */
#import <UIKit/UIKit.h>
#import <CoreFoundation/CoreFoundation.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include "../patches/async-alert-uikit-v20.inc"

static void record(const char *line)
{
    fputs(line, stderr);
    NSString *path = [NSHomeDirectory() stringByAppendingPathComponent:@"Documents/native-alert-regression.log"];
    FILE *file = fopen(path.fileSystemRepresentation, "a");
    if (file) { fputs(line, file); fclose(file); }
}

static void uncaughtException(NSException *exception)
{
    NSString *description = [NSString stringWithFormat:
        @"[NATIVE ALERT REGRESSION] FAIL uncaught %@: %@\n%@\n",
        exception.name, exception.reason, exception.callStackSymbols];
    record(description.UTF8String);
    _exit(82);
}

#define REQUIRE(condition, label) do { if (!(condition)) { \
    record("[NATIVE ALERT REGRESSION] FAIL " label "\n"); \
    fflush(stderr); _exit(81); } } while (0)

@interface TouchHLETestSceneDelegate : UIResponder <UIWindowSceneDelegate>
@property(nonatomic, strong) UIWindow *window;
@property(nonatomic, strong) NSTimer *heartbeatTimer;
@property(nonatomic) unsigned heartbeats;
@property(nonatomic) uint64_t firstTestToken;
@end
@implementation TouchHLETestSceneDelegate
- (void)scene:(UIScene *)scene willConnectToSession:(UISceneSession *)session
    options:(UISceneConnectionOptions *)options
{
    (void)session; (void)options;
    self.window = [[UIWindow alloc] initWithWindowScene:(UIWindowScene *)scene];
    self.window.rootViewController = [UIViewController new];
    [self.window makeKeyAndVisible];
    [self performSelector:@selector(runTests) withObject:nil afterDelay:0.3];
}
- (void)runTests
{
    NSSetUncaughtExceptionHandler(uncaughtException);
    record("[NATIVE ALERT REGRESSION] START actual UIKit simulator\n");
    __weak TouchHLETestSceneDelegate *weakSelf = self;
    self.heartbeats = 0;
    self.heartbeatTimer = [NSTimer scheduledTimerWithTimeInterval:0.01 repeats:YES
        block:^(NSTimer *unused) { (void)unused; weakSelf.heartbeats++; }];
    char title[] = "Startup popup";
    char first[] = "OK";
    char second[] = "Later";
    const char *buttons[] = {first, second};
    uint64_t token = TouchHLE_BeginAsyncAlertV20(self.window, title, "Message", buttons, 2);
    REQUIRE(token != 0, "create token");
    self.firstTestToken = token;
    memset(title, 'x', sizeof(title) - 1);
    memset(first, 'x', sizeof(first) - 1);
    // Return to UIKit's ordinary loop, exactly as the new async show does.
    // Do not impose a short nested-loop timing budget on a cold simulator.
    [self performSelector:@selector(checkFirstPresentation) withObject:nil afterDelay:1.0];
}
- (void)checkFirstPresentation
{
    uint64_t token = self.firstTestToken;
    TouchHLEAlertStateV20 *state = touchHLEAlertsV20[@(token)];
    REQUIRE(self.heartbeats >= 2, "native run loop continues");
    REQUIRE([state.title isEqualToString:@"Startup popup"] &&
            [state.buttonTitles[0] isEqualToString:@"OK"], "copied strings outlive caller");
    REQUIRE(state.window.windowScene == self.window.windowScene &&
            state.window.isKeyWindow && state.window.windowLevel > UIWindowLevelAlert,
            "key window above game controls in correct scene");
    REQUIRE(state.controller.view.window == state.window &&
            state.controller.actions.count == 2, "real UIKit popup presented");
    REQUIRE(TouchHLE_PollAsyncAlertV20(token) == -1, "no synthetic selection");
    TouchHLE_RecordAlertSelectionV20(state, 1);
    TouchHLE_RecordAlertSelectionV20(state, 0);
    REQUIRE(TouchHLE_PollAsyncAlertV20(token) == 1, "one original selected index");
    REQUIRE(TouchHLE_PollAsyncAlertV20(token) == -2, "selection consumed once");
    [self performSelector:@selector(checkOtherCases) withObject:nil afterDelay:0.1];
}
- (void)checkOtherCases
{
    REQUIRE(self.window.isKeyWindow, "restore original key window");
    record("[NATIVE ALERT REGRESSION] PASS 01 nonblocking presentation and copied ownership\n");

    const char *ok[] = {"OK"};
    uint64_t token = TouchHLE_BeginAsyncAlertV20(self.window, "Dismissed by game", "", ok, 1);
    TouchHLEAlertStateV20 *state = touchHLEAlertsV20[@(token)];
    TouchHLE_DismissAsyncAlertV20(token);
    TouchHLE_DismissAsyncAlertV20(token);
    TouchHLE_RecordAlertSelectionV20(state, 0);
    REQUIRE(TouchHLE_PollAsyncAlertV20(token) == -2, "programmatic dismissal has no click");
    REQUIRE(touchHLEAlertsV20.count == 0 && touchHLEAlertQueueV20.count == 0,
            "dismiss clears native ownership");
    record("[NATIVE ALERT REGRESSION] PASS 02 programmatic and duplicate dismissal\n");

    uint64_t firstToken = TouchHLE_BeginAsyncAlertV20(self.window, "First", "", ok, 1);
    uint64_t nextToken = TouchHLE_BeginAsyncAlertV20(self.window, "Second", "", ok, 1);
    REQUIRE(touchHLEActiveAlertV20 == firstToken && touchHLEAlertQueueV20.count == 1,
            "overlapping presentations queued");
    state = touchHLEAlertsV20[@(firstToken)];
    TouchHLE_RecordAlertSelectionV20(state, 0);
    REQUIRE(TouchHLE_PollAsyncAlertV20(firstToken) == 0 &&
            touchHLEActiveAlertV20 == nextToken, "next popup follows completed first popup");
    TouchHLE_RecordAlertSelectionV20(state, 0);
    REQUIRE(TouchHLE_PollAsyncAlertV20(firstToken) == -2, "stale event rejected");
    TouchHLE_DismissAsyncAlertV20(nextToken);
    REQUIRE(self.window.isKeyWindow, "queue cleanup restores host key window");
    record("[NATIVE ALERT REGRESSION] PASS 03 queued popup and stale event protection\n");

    firstToken = TouchHLE_BeginAsyncAlertV20(self.window, "Exit cleanup", "", ok, 1);
    nextToken = TouchHLE_BeginAsyncAlertV20(self.window, "Queued cleanup", "", ok, 1);
    TouchHLE_ResetAsyncAlertsV20();
    REQUIRE(touchHLEAlertsV20.count == 0 && touchHLEAlertQueueV20.count == 0 &&
            touchHLEActiveAlertV20 == 0 && self.window.isKeyWindow, "core exit cleanup");
    token = TouchHLE_BeginAsyncAlertV20(self.window, "Relaunch", "", ok, 1);
    REQUIRE(token > firstToken && token > nextToken, "tokens never reused on relaunch");
    TouchHLE_DismissAsyncAlertV20(token);
    REQUIRE(TouchHLE_BeginAsyncAlertV20(self.window, "Invalid", "", ok, 0) == 0,
            "invalid request rejected");
    [self.heartbeatTimer invalidate];
    self.heartbeatTimer = nil;
    record("[NATIVE ALERT REGRESSION] PASS 04 exit cleanup and token isolation\n");
    record("[NATIVE ALERT REGRESSION] ALL PASS 4\n");
    fflush(stderr);
    /* State/event-boundary test, not a claim that hardware touch was tested. */
    _exit(0);
}
@end

@interface TouchHLETestAppDelegate : UIResponder <UIApplicationDelegate>
@end
@implementation TouchHLETestAppDelegate
- (UISceneConfiguration *)application:(UIApplication *)application
    configurationForConnectingSceneSession:(UISceneSession *)session
    options:(UISceneConnectionOptions *)options
{
    (void)application; (void)options;
    UISceneConfiguration *config = [[UISceneConfiguration alloc]
        initWithName:@"Regression" sessionRole:session.role];
    config.delegateClass = [TouchHLETestSceneDelegate class];
    return config;
}
@end

int main(int argc, char **argv)
{
    @autoreleasepool {
        return UIApplicationMain(argc, argv, nil, NSStringFromClass([TouchHLETestAppDelegate class]));
    }
}
